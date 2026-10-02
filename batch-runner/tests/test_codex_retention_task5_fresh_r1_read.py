"""Closed fifth-cell reads with real validators and synthetic immutable bytes."""

import builtins
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import codex_retention_fresh_r1_result_intake as reader
import codex_retention_task5_fresh_r1 as producer
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from core.cost_receipts import CostReceipt
from core.reference_integrity import ReferenceIntegrityError
from .test_codex_budget_pilot_retention import TOKEN, offline  # noqa: F401
from .test_codex_retention_fresh_r1_result_intake import FreshResultHF
from .test_codex_retention_fresh_r1_terminal_observation import TerminalHF
from .test_codex_retention_result_intake import CLAIM_HEAD, OUTPUT_HEAD, TERMINAL_HEAD, FILE, PRIVATE

ci, retained, output, owned, intake = reader.ci, reader.retained, reader.output, reader.owned, reader.intake
TASK5_FILE = "deliverable_files/" + intake.registration.TASK5 + "/report.txt"


def _task5_fixture(plan, *, terminal=False, **options):
    """Rebind only authored synthetic payloads before sealing their identities."""
    api = (TerminalHF if terminal else FreshResultHF)(plan, binding=reader.TASK5_FRESH_R1, **options)
    row = api.payload["results"][0]
    api.payload["ordered_task_ids"] = [intake.registration.TASK5]
    row["task_id"] = intake.registration.TASK5
    row["deliverable_files"] = [TASK5_FILE]
    row["deliverable_file_records"] = [{"path": TASK5_FILE, **owned._identity(PRIVATE)}]
    if FILE in api.files:
        api.files[TASK5_FILE] = api.files.pop(FILE)
    if intake.LEDGER in api.files:
        ledger = json.loads(api.files[intake.LEDGER])
        ledger["task_id"] = intake.registration.TASK5
        api.files[intake.LEDGER] = (json.dumps(ledger) + "\n").encode()
        api.payload["cost_ledger"]["sha256"] = owned._identity(api.files[intake.LEDGER])["sha256"]
    if intake.RESULT in api.files:
        api.bind_payload()
    api.seed()
    return api


def test_task5_fresh_r1_reads_only_its_fixed_result_or_terminal(tmp_path, monkeypatch, capsys):
    effects, transports, errors = [], [], []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("Task5 reader crossed a live, paid, admission or payload boundary")

    for owner, names in (
        (ci, ("execute", "verify_approval", "verify_job_origin", "verify_terminal")),
        (producer, ("execute", "_predecessor", "verify_terminal")),
        (producer._Task5FreshR1Admission, ("__init__",)), (ci._Admission, ("__init__",)),
        (ci.LocalTransport, ("github_job_token", "authority_opener", "github", "azure")),
        (owned.LocalTransport, ("clock", "child", "process")),
        (ci.preparation, ("prepare_packet", "verify_packet")), (ci.historical, ("observe",)),
        (ci.controller, ("execute_first_cell", "stage_runtime", "_deadline")),
        (CodexTaskDeadlineStore, ("__init__",)), (CodexTaskDeadline, ("admit_attempt",)),
        (intake.retained_reader, ("prepare", "main")), (output, ("_hf_client",)),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)

    # Preserve original classes/relative frames if an unexpected CLI refusal
    # hides its cause; do not log exception strings, paths, bodies or credentials.
    def observed(function):
        def call(**kwargs):
            try:
                return function(**kwargs)
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
                chain, current = [], error
                while current is not None and len(chain) < 6:
                    frames, trace = [], current.__traceback__
                    while trace is not None:
                        path = Path(trace.tb_frame.f_code.co_filename)
                        if path.is_relative_to(ci.ROOT):
                            frames.append([path.relative_to(ci.ROOT).as_posix(), trace.tb_lineno])
                        trace = trace.tb_next
                    chain.append({"class": type(current).__name__, "frames": frames})
                    current = current.__cause__ or current.__context__
                errors.append({"operation": function.__name__, "chain": chain,
                    "remote_commits": sum(len(api.commits) for api in transports)})
                raise
        return call

    monkeypatch.setattr(reader, "read_result", observed(reader.read_result))
    monkeypatch.setattr(reader, "observe_terminal", observed(reader.observe_terminal))
    binding = reader.TASK5_FRESH_R1
    assert binding.expectation == ci.TerminalExpectation(
        "9a53e9c0ae7b50400f2b27d514207e489b237cc5b5195ff8e36fcc4ea920370b",
        "e5e338aa22c247133936fa075c2def7bffb95173",
        "0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_fresh_r1")
    assert (binding.ordinal, binding.repetition, binding.retention_bundle, binding.run_id,
            binding.execution_job_id) == (4, 1, "fresh", "37032230813", 110933285330)
    assert binding.original_input_bundle_sha256 == "757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3"
    assert binding.materialized_grader_source_sha256 == "a820cd9e3a8e74e684aa65a710e5a7b0649ce0435fe425a070a0eb6d8b30145e"
    assert producer.PREDECESSOR["terminal_commit"] == "e55fac5d60191167dd66688510ec0fef472e594d"
    source = reader.reader_identity(binding=binding)
    assert source["producer_task5_fresh_r1_sha256"] == "9919fda7728e84d0d707fe6a4b23a8a601c04b1e5241bcc83387b9acd20f0f5a"
    assert reader.reader_identity(binding=reader.KEEP_R2) == {
        key: value for key, value in source.items() if key != "producer_task5_fresh_r1_sha256"}
    assert {key: source[key] for key in reader.FROZEN} == {key: pair[1] for key, pair in reader.FROZEN.items()}
    assert reader.fresh._publication_task_id(producer._publication_binding()) == intake.registration.TASK5
    plan = intake.registration.compile_plan()

    def make(*, terminal=False, **options):
        api = _task5_fixture(plan, terminal=terminal, **options)
        transports.append(api)
        return api

    def read(api, name, *, terminal=False, **changes):
        options = dict(expectation=binding.expectation, binding=binding, destination=tmp_path / name,
            expected_reader_sha256=source["module_sha256"], terminal_revision=TERMINAL_HEAD, _test_api=api)
        return (reader.observe_terminal if terminal else reader.read_result)(**{**options, **changes})

    def refuse(api, name, reason, *, terminal=False, **changes):
        with pytest.raises(output.OutputPublicationRefused) as refused:
            read(api, name, terminal=terminal, **changes)
        assert refused.value.args == (reason,), {"case": name, "cause": errors[-1:]}
        assert not (tmp_path / name / (binding.terminal_marker if terminal else binding.result_marker)).exists()

    def argv(name, terminal=False):
        return ["--observe-terminal" if terminal else "--read", "--discover-terminal",
            "--expected-producer-source", binding.expectation.source_sha,
            "--expected-request-sha256", binding.expectation.request_sha256, "--cell-id", binding.expectation.cell_id,
            "--expected-reader-sha256", source["module_sha256"], "--output", str(tmp_path / name)]

    def captured(api):
        text = capsys.readouterr()
        assert text.err == ""
        assert all(secret not in text.out for secret in (str(tmp_path), api.repo, TOKEN, PRIVATE.decode().strip(),
                                                        TASK5_FILE, FILE, "SECRET-LIKE-ERROR"))
        return json.loads(text.out)

    api = make()
    with monkeypatch.context() as early:
        early.setattr(retained, "_session", forbidden)
        assert reader.main([], _test_api=api) == 0
        assert captured(api)["cell_id"] == reader.FRESH_R1.expectation.cell_id
        for index, (changes, reason) in enumerate((
            ({"binding": replace(binding)}, "fixed_fresh_read_binding_required"),
            ({"binding": replace(binding, ordinal=True)}, "fixed_fresh_read_binding_required"),
            ({"expectation": replace(binding.expectation, cell_id="unknown")}, "fresh_result_expected_cell_mismatch"),
            ({"expectation": replace(binding.expectation, source_sha=reader.KEEP_R2.expectation.source_sha)}, "fresh_result_expected_producer_mismatch"),
            ({"expectation": replace(binding.expectation, request_sha256=reader.KEEP_R2.expectation.request_sha256)}, "fresh_result_expected_request_mismatch"),
            ({"expected_reader_sha256": "d042c02228f2430d4129ed37b3fb453cf9792bbde269a28bd10c6daf8f00b900"}, "fresh_result_reader_bytes_mismatch"),
            ({"discover_terminal": 1, "terminal_revision": None}, "one_terminal_revision_or_discovery_required"),
            ({"discover_terminal": True}, "one_terminal_revision_or_discovery_required"),
        )):
            for terminal in (False, True):
                refuse(api, f"early-{index}-{terminal}", reason, terminal=terminal, **changes)
        wrong = deepcopy(plan)
        wrong["cells"][4]["control"]["retention_bundle"] = "keep"
        early.setattr(intake.registration, "compile_plan", lambda: wrong)
        for terminal in (False, True):
            refuse(api, "wrong-treatment-" + str(terminal), "fresh_result_registered_cell_mismatch", terminal=terminal)
    assert not api.calls and not effects

    real_bytes, real_import = output._bytes, builtins.__import__
    for bad_path, _ in (reader.R2_PRODUCER_PIN, reader.KEEP_R2_PRODUCER_PIN, reader.TASK5_PRODUCER_PIN):
        def changed_bytes(path, **kwargs):
            data = real_bytes(path, **kwargs)
            return data + b"\n" if Path(path) == bad_path else data

        def no_lazy_import(name, *args, **kwargs):
            if name in {"codex_retention_task4_fresh_r2", "codex_retention_task4_keep_r2", "codex_retention_task5_fresh_r1"}:
                return forbidden()
            return real_import(name, *args, **kwargs)

        with monkeypatch.context() as corrupt:
            corrupt.setattr(output, "_bytes", changed_bytes)
            corrupt.setattr(builtins, "__import__", no_lazy_import)
            corrupt.setattr(retained, "_session", forbidden)
            for terminal in (False, True):
                refuse(api, bad_path.stem + str(terminal), "fresh_result_reader_bytes_mismatch", terminal=terminal)
            with pytest.raises(output.OutputPublicationRefused, match="^fresh_result_reader_bytes_mismatch$"):
                reader._producer(binding)
    assert not api.calls and not effects
    monkeypatch.setenv("HF_TOKEN", TOKEN)  # Synthetic transport only, never a live token.
    receipt = ci.project_cost_receipt(CostReceipt(status="partial", model_calls=2,
        known_cost_usd=Decimal("0.01"), model_cost_usd=Decimal("0.01"),
        usage={"input_tokens": 12, "cached_input_tokens": 8, "output_tokens": 3, "reasoning_tokens": 2},
        missing_reasons=("synthetic_missing_cost",)).as_dict())
    success_api = make(receipt=receipt, with_ledger=True)
    code = reader.main(argv("result"), _test_api=success_api)
    success = captured(success_api)
    assert code == 0, {"stage": "success_payload_readback", "cause": errors[-1:]}
    assert success["intake_verified"] is True and success["status"] == "succeeded"
    assert success["format"] == binding.result_format and "terminal_verified" not in success
    assert success["result"]["registered_config_sha256"] == plan["cells"][4]["config_sha256"]
    assert output._hash(success["result"]["result_fingerprint"])
    marker = tmp_path / "result" / binding.result_marker
    assert success["intake_sha256"] == owned._identity(marker.read_bytes())["sha256"]
    assert "intake_verified" not in json.loads(marker.read_bytes())
    assert (tmp_path / "result" / TASK5_FILE).read_bytes() == PRIVATE
    assert (tmp_path / "result").stat().st_mode & 0o777 == 0o700
    assert marker.stat().st_mode & 0o777 == 0o600
    assert success["receipt"] == receipt and success["accounting"] == "partial"
    controls = {producer.CLAIM, producer.TERMINAL, producer.OUTPUT + "/" + output.MANIFEST}
    assert {name for _, name in success_api.downloads} == {
        *controls, *(producer.OUTPUT + "/" + name for name in success_api.files)}
    evidence = [(success_api, success)]
    for index, (status, declared, cost, exit_code) in enumerate((
        ("failed", "none", None, 1), ("stopped", "none", receipt, None),
        ("failed", "partial", receipt, 137), ("stopped", "result", None, -15),
    )):
        terminal_api = make(terminal=True, status=status, declared=declared, receipt=cost, exit_code=exit_code)
        with monkeypatch.context() as control_only:
            for owner, name in ((intake, "_payload"), (intake.retained_reader, "_fetch"), (output, "_ledger")):
                control_only.setattr(owner, name, forbidden)
            code = reader.main(argv("terminal-" + str(index), True), _test_api=terminal_api)
        record = captured(terminal_api)
        assert code == 0, {"stage": "unsuccessful_controls", "case": index, "cause": errors[-1:]}
        assert record["terminal_verified"] is True and record["outcome"] == "terminal_verified"
        assert record["status"] == status and record["exit_code"] == exit_code
        assert record["receipt"] == cost and record["missing"] == terminal_api.summary["missing"]
        assert record["declared_payload_roles"] == {"inference_result": int(declared != "none"),
            "ledger": int(declared == "partial"), "deliverables": int(declared == "partial")}
        assert record["payload_bodies_verified"] is record["grading_input_ready"] is False
        assert not {"intake_verified", "judge_ready", "result", "files"} & set(record)
        assert len(terminal_api.downloads) == 3 and {name for _, name in terminal_api.downloads} == controls
        saved = tmp_path / ("terminal-" + str(index)) / binding.terminal_marker
        assert record["observation_sha256"] == owned._identity(saved.read_bytes())["sha256"]
        assert saved.stat().st_mode & 0o777 == 0o600
        evidence.append((terminal_api, record))
        refuse(terminal_api, "no-success-fallback-" + str(index), "fresh_result_success_required")
    refuse(success_api, "no-terminal-fallback", "fresh_terminal_unsuccessful_required", terminal=True)
    no_result = deepcopy(success_api.summary)
    no_result["files"] = []
    with pytest.raises(output.OutputPublicationRefused, match="^retention_result_payload_required$"):
        reader._summary(no_result, binding=binding)
    for transport, record in evidence:
        assert record["ordinal"] == 4 and record["cell_id"] == binding.expectation.cell_id
        assert record["producer_source_sha"] == binding.expectation.source_sha
        assert record["request_sha256"] == binding.expectation.request_sha256
        assert record["recorded_provider_job_id"] == record["expected_execution_job_id"] == 110933285330
        assert record["recorded_provider_run_id"] == record["expected_provider"]["run_id"] == "37032230813"
        assert record["expected_provider"]["attempt"] == 1 and record["expected_provider"]["workflow_id"] == 370228282
        assert record["terminal_commit"] == TERMINAL_HEAD != transport.head
        assert record["predecessor"] == producer.PREDECESSOR and record["reader"] == source
        assert record["supplied_request_binding"] == reader._request_context(binding)
        assert record["writer_acknowledgment"] == "not_established" and record["recorded_publication_acknowledged"] is True
        assert record["proof"] == "verified_publication_derived_not_independent_provider_authentication"
        assert record["grade"] is record["http_request_count"] is None and record["commands"] == []
        assert all(record[key] is False for key in ("fresh_origin_authentication", "prepared_input_independently_verified",
            "git_parent_cas_independently_verified", "launch_authorized", "admission_attempted", "replay_authorized",
            "grading_launched", "invoice_complete"))
        assert [(revision, paths) for revision, paths in transport.path_reads if revision == retained.BRANCH] == [
            (retained.BRANCH, (producer.TERMINAL,))]

    for terminal in (False, True):
        for job in (reader.KEEP_R2.execution_job_id, True, float(binding.execution_job_id)):
            bad = make(terminal=terminal)
            for authority in (bad.claim["authority"], bad.terminal["authority"]):
                authority["provider_job_id"] = job
            bad.seed()
            reason = ("fresh_terminal_execution_job_mismatch" if terminal else "fresh_result_execution_job_mismatch")
            refuse(bad, f"job-{terminal}-{job}", reason if type(job) is int else
                   "fresh_result_authority_binding_mismatch", terminal=terminal)
        for fault, reason in (("source", "fresh_result_completion_mismatch"), ("cell", "fresh_result_completion_mismatch"),
            ("request", "fresh_result_terminal_binding_mismatch"), ("run", "fresh_result_authority_binding_mismatch"),
            ("cleanup", "fresh_result_completion_mismatch"), ("grade", "fresh_result_completion_mismatch"),
            ("parent-grade1", "fresh_result_predecessor_mismatch"), ("parent-grade2", "fresh_result_predecessor_mismatch"),
            ("predecessor", "fresh_result_predecessor_mismatch")):
            bad = make(terminal=terminal)
            if fault in {"source", "cell", "cleanup", "grade"}:
                key, value = {"source": ("source_sha", reader.KEEP_R2.expectation.source_sha),
                    "cell": ("cell_id", reader.KEEP_R2.expectation.cell_id), "cleanup": ("cleanup_confirmed", 1),
                    "grade": ("grade", 0)}[fault]
                bad.summary[key] = value
            elif fault == "request":
                bad.terminal["request_sha256"] = reader.KEEP_R2.expectation.request_sha256
            elif fault == "run":
                for authority in (bad.claim["authority"], bad.terminal["authority"]):
                    authority["provider_run_id"] = reader.KEEP_R2.run_id
            elif fault == "predecessor":
                bad.claim["predecessor"]["execution_job_id"] = float(producer.PREDECESSOR["execution_job_id"])
            else:
                bad.claim["expected_parent"] = ("40712e0980cc05c31688fdbb98c693774fb90c0d" if fault == "parent-grade1"
                                                else "76f51d0464b3c90d9ff80b78b656b9e7d45a0b6e")
            bad.seed()
            refuse(bad, fault + str(terminal), reason, terminal=terminal)

    for fault, reason in (("claim-hash", "payload_identity_mismatch"), ("object-history", "remote_output_history_mismatch"),
        ("terminal-history", "retention_control_history_mismatch"), ("missing-claim", "terminal_or_claim_missing"),
        ("missing-manifest", "terminal_or_claim_missing"), ("missing-object", "remote_output_objects_missing"),
        ("running", "fresh_terminal_unsuccessful_required"), ("unacknowledged", "fresh_result_terminal_binding_mismatch")):
        bad = make(terminal=True)
        if fault == "claim-hash":
            bad.terminal["claim_identity"]["sha256"] = "0" * 64
        elif fault == "object-history":
            bad.writers[TERMINAL_HEAD][producer.OUTPUT + "/" + TASK5_FILE] = TERMINAL_HEAD
        elif fault == "terminal-history":
            bad.writers[TERMINAL_HEAD][producer.TERMINAL] = OUTPUT_HEAD
        elif fault.startswith("missing-"):
            bad.omit_metadata = {"missing-claim": (CLAIM_HEAD, producer.CLAIM),
                "missing-manifest": (OUTPUT_HEAD, producer.OUTPUT + "/" + output.MANIFEST),
                "missing-object": (TERMINAL_HEAD, producer.OUTPUT + "/" + TASK5_FILE)}[fault]
        elif fault == "running":
            bad.summary["status"] = "running"
        else:
            bad.terminal["publication_acknowledged"] = False
        bad.trees[TERMINAL_HEAD][producer.TERMINAL] = retained._encoded(bad.terminal)
        refuse(bad, fault, reason, terminal=True)
        assert {name for _, name in bad.downloads} <= controls

    for terminal in (False, True):
        missing = make(terminal=True)
        missing.omit_metadata = (retained.BRANCH, producer.TERMINAL)
        assert reader.main(argv("not-ready-" + str(terminal), terminal), _test_api=missing) == 2
        assert captured(missing)["reason"] == "fresh_result_terminal_not_ready"
        assert len(missing.path_reads) == 1 and not missing.downloads
        for fault, reason in (("duplicate", "fresh_result_output_bounds_exceeded"),
            ("size-type", "fresh_result_output_identity_refused"), ("record-size", "retention_result_record_bounds_exceeded"),
            ("private", "retention_result_private_state_refused"), ("total", "fresh_result_output_bounds_exceeded")):
            summary = deepcopy(make(terminal=terminal).summary)
            if fault == "duplicate":
                summary["files"].append(deepcopy(summary["files"][0]))
            elif fault == "size-type":
                summary["files"][0]["size"] = True
            elif fault == "record-size":
                next(item for item in summary["files"] if item["path"] == intake.RESULT)["size"] = output.MAX_RECORD_BYTES + 1
            elif fault == "private":
                next(item for item in summary["files"] if item["path"] == TASK5_FILE)["path"] = TASK5_FILE.replace("report.txt", "HOME/auth.json")
            else:
                summary["files"] = [{"path": f"deliverable_files/{intake.registration.TASK5}/{index}.txt",
                    "size": output.MAX_FILE_BYTES, "sha256": "0" * 64} for index in range(3)]
            with pytest.raises(output.OutputPublicationRefused, match="^" + reason + "$"):
                (reader._terminal_summary if terminal else reader._summary)(summary, binding=binding)
        summary = deepcopy(make(terminal=terminal).summary)
        next(item for item in summary["files"] if item["path"] == TASK5_FILE)["path"] = FILE
        with pytest.raises(ValueError, match="^deliverable path must stay under deliverable_files/" + intake.registration.TASK5 + "/$"):
            (reader._terminal_summary if terminal else reader._summary)(summary, binding=binding)
        redacted = make(terminal=terminal)
        redacted.read_error = ValueError("SECRET-LIKE-ERROR")
        assert reader.main(argv("redacted-" + str(terminal), terminal), _test_api=redacted) == 2
        assert captured(redacted)["reason"] == ("fresh_terminal_observation_refused" if terminal else "fresh_result_intake_refused")

    for fault, reason in (("runtime", "retention_result_runtime_identity_mismatch"),
                         ("corrupt", "retained_file_identity_mismatch"), ("ledger", "ledger_cell_mismatch")):
        bad = make(with_ledger=True)
        if fault == "runtime":
            bad.payload["ordered_task_ids"] = [intake.registration.TASK4]
            bad.bind_payload()
        elif fault == "corrupt":
            bad.corrupt = producer.OUTPUT + "/" + intake.RESULT
        else:
            row = json.loads(bad.files[intake.LEDGER])
            row["task_id"] = intake.registration.TASK4
            bad.files[intake.LEDGER] = (json.dumps(row) + "\n").encode()
            bad.payload["cost_ledger"]["sha256"] = owned._identity(bad.files[intake.LEDGER])["sha256"]
            bad.bind_payload()
        bad.seed()
        refuse(bad, "payload-" + fault, reason)
    bad = make()
    bad.payload["result_fingerprint"] = "0" * 64
    bad.files[intake.RESULT] = (json.dumps(bad.payload) + "\n").encode()
    bad.seed()
    with pytest.raises(ValueError, match="^inference result fingerprint does not match payload$"):
        read(bad, "payload-fingerprint")
    assert not (tmp_path / "payload-fingerprint" / binding.result_marker).exists()

    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "linked-parent"
    link.symlink_to(outside, target_is_directory=True)
    for terminal, api, name in ((False, success_api, "result"), (True, terminal_api, "terminal-3")):
        calls = list(api.calls)
        existing_marker = tmp_path / name / (binding.terminal_marker if terminal else binding.result_marker)
        saved_marker = existing_marker.read_bytes()
        with pytest.raises(output.OutputPublicationRefused, match="^new_result_destination_required$"):
            read(api, name, terminal=terminal)
        assert existing_marker.read_bytes() == saved_marker
        with pytest.raises(ReferenceIntegrityError):
            read(api, "symlink", terminal=terminal, destination=link / "unused")
        assert api.calls == calls and not (outside / "unused").exists()
        real_write = reader._write_no_clobber
        marker_name = binding.terminal_marker if terminal else binding.result_marker

        def corrupt_marker(path, data, **kwargs):
            return real_write(path, data + b"\n" if path.name == marker_name else data, **kwargs)

        ambiguous = make(terminal=terminal)
        with monkeypatch.context() as ack:
            ack.setattr(reader, "_write_no_clobber", corrupt_marker)
            with pytest.raises(output.OutputPublicationRefused, match="^" + (
                "fresh_terminal_observation_unconfirmed" if terminal else "fresh_result_completion_acknowledgment_unconfirmed") + "$"):
                read(ambiguous, "ambiguous-" + str(terminal), terminal=terminal)
        calls = list(ambiguous.calls)
        with pytest.raises(output.OutputPublicationRefused, match="^new_result_destination_required$"):
            read(ambiguous, "ambiguous-" + str(terminal), terminal=terminal)
        assert ambiguous.calls == calls

    # Small old-binding checks only; none of the old delivered suites is called.
    for old in (reader.FRESH_R1, reader.FRESH_R2, reader.KEEP_R2):
        api = FreshResultHF(plan, binding=old)
        transports.append(api)
        kwargs = {} if old is reader.FRESH_R1 else {"binding": old}
        result = reader.read_result(expectation=old.expectation, destination=tmp_path / ("old-" + str(old.ordinal)),
            expected_reader_sha256=source["module_sha256"], terminal_revision=TERMINAL_HEAD, _test_api=api, **kwargs)
        assert result["intake_verified"] is True and result["cell_id"] == old.expectation.cell_id
        if old is reader.FRESH_R1:
            assert result["recorded_provider_job_id"] == 123456 and "expected_execution_job_id" not in result
        else:
            assert result["expected_execution_job_id"] == old.execution_job_id
        summary = deepcopy(api.summary)
        next(item for item in summary["files"] if item["path"] == FILE)["path"] = TASK5_FILE
        with pytest.raises(ValueError, match="^deliverable path must stay under deliverable_files/" + intake.registration.TASK4 + "/$"):
            reader._summary(summary, binding=old)
    assert not effects and all(not api.commits for api in transports)
    print(json.dumps({"scope": "synthetic_task5_reader_only", "success_payload_verified": True,
        "failed_stopped_three_controls_only": True, "fixed_job_both_modes": True, "old_defaults_preserved": True,
        "private_no_clobber_readback": True, "live_effects": len(effects)}, sort_keys=True))


def test_task5_reader_current_source_keeps_historical_grade_evidence(tmp_path, monkeypatch):
    import codex_retention_grade_readout as observer
    import gpt54_disposable_checkout as source_checkout

    bridge = observer.bridge
    fixed = bridge._fixed("retention/keep-r2")
    historical = deepcopy((bridge.RESULT, bridge.PARENT, bridge.READER, fixed.RESULT, fixed.PARENT, fixed.READER))
    assert bridge.fixed_evidence_sha256() == "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d"
    assert bridge.fixed_evidence_sha256(fixed.SELECTOR) == "25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0"
    assert fixed.RESULT["intake_sha256"] == "4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4"
    assert fixed.READER["module_sha256"] == "5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583"
    assert observer.CURRENT_DEPENDENCIES["codex_retention_fresh_r1_result_intake.py"] == reader.reader_identity()["module_sha256"]
    for name, digest in observer.CURRENT_DEPENDENCIES.items():
        assert hashlib.sha256((bridge.ROOT / "batch-runner" / name).read_bytes()).hexdigest() == digest
    common = tmp_path / "git-common"
    common.mkdir()
    expected = "a" * 40
    state = {"head": expected, "diff": b"", "status": b"", "config": b""}

    def git(path, *command, ok=(0,)):
        assert Path(path) == bridge.ROOT
        answers = {("rev-parse", "--show-toplevel"): os.fsencode(bridge.ROOT) + b"\n",
            ("rev-parse", "--path-format=absolute", "--git-common-dir"): os.fsencode(common) + b"\n",
            ("rev-parse", "HEAD"): (state["head"] + "\n").encode(),
            ("diff", "--name-only", "HEAD", "--"): state["diff"],
            ("status", "--porcelain", "--untracked-files=normal"): state["status"],
            ("config", "--name-only", "--get-regexp",
             r"^(filter\.|include\.|includeif\.|extensions\.partialclone$|remote\..*\.promisor$|core\.alternaterefscommand$)"): state["config"]}
        assert command in answers  # Synthetic Git transport, real checkout/source predicates.
        return SimpleNamespace(stdout=answers[command], returncode=0)

    monkeypatch.setattr(source_checkout, "_git", git)
    monkeypatch.setattr(owned, "_git", git)
    for selector in (observer.SELECTOR, observer.KEEP_R2_SELECTOR):
        observer._source_current(expected, selector=selector)
    with pytest.raises(output.OutputPublicationRefused, match="^reviewed_retention_reader_required$"):
        bridge._source(bridge.compile_request(expected, selector=fixed.SELECTOR))
    real_bytes = output._bytes

    def corrupt(path, **kwargs):
        data = real_bytes(path, **kwargs)
        return data + b"\n" if Path(path).name == "codex_retention_fresh_r1_result_intake.py" else data

    with monkeypatch.context() as changed:
        changed.setattr(output, "_bytes", corrupt)
        with pytest.raises(output.OutputPublicationRefused, match="^reviewed_retention_observer_dependency_required$"):
            observer._source_current(expected, selector=observer.KEEP_R2_SELECTOR)
    for name, value, reason in (("head", "e" * 40, "retention_grade_source_changed"),
        ("diff", b"tracked.py\n", "retention_grade_source_changed"),
        ("status", b"?? untracked.py\n", "clean_retention_grade_source_required"),
        ("config", b"include.path\n", "checkout filters, includes or partial-clone configuration are unsupported")):
        before = state[name]
        state[name] = value
        with pytest.raises(ValueError, match="^" + reason + "$"):
            observer._source_current(expected)
        state[name] = before
    assert historical == (bridge.RESULT, bridge.PARENT, bridge.READER, fixed.RESULT, fixed.PARENT, fixed.READER)
    print("OFFLINE current reader pin verified; historical 25d259/1ced90/intake4d33 unchanged; no paid or live effects")
