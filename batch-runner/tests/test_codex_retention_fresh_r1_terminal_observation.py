"""Unsuccessful fresh/r1 controls only; all payload and execution effects fail."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json

import pytest

import codex_retention_fresh_r1_result_intake as reader
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from core.cost_receipts import CostReceipt
from .test_codex_budget_pilot_retention import TOKEN, offline  # noqa: F401
from .test_codex_retention_fresh_r1_result_intake import FreshResultHF
from .test_codex_retention_result_intake import CLAIM_HEAD, OUTPUT_HEAD, TERMINAL_HEAD, FILE, PRIVATE

fresh, ci, retained, output, owned = reader.fresh, reader.ci, reader.retained, reader.output, reader.owned
intake = reader.intake
CONTROLS = {fresh.TERMINAL, fresh.CLAIM, fresh.OUTPUT + "/" + output.MANIFEST}


class TerminalHF(FreshResultHF):
    """Real producer serializers with synthetic unsuccessful control records."""

    def __init__(self, plan, *, status="failed", declared="partial", receipt=None, exit_code=137,
                 binding=reader.FRESH_R1, terminal_head=TERMINAL_HEAD):
        super().__init__(plan, receipt=receipt, with_ledger=declared == "partial", binding=binding,
                         terminal_head=terminal_head)
        self.payload["results"][0]["status"] = "error"
        self.bind_payload()
        if declared == "none":
            self.files = {}
        elif declared == "result":
            self.files = {intake.RESULT: self.files[intake.RESULT]}
        for authority in (self.claim["authority"], self.terminal["authority"]):
            authority["provider_job_id"] = binding.execution_job_id
        self.summary.update(status=status, exit_code=exit_code)
        self.summary["missing"] = ([] if intake.RESULT in self.files else ["bound_inference_result", "validated_deliverables"])
        self.summary["missing"] += ([] if intake.LEDGER in self.files else ["bound_ledger_export"])
        self.summary["missing"] += ([] if receipt is not None and receipt["usage"] is not None else ["usage"])
        self.omit_metadata = None
        self.seed()

    def get_paths_info(self, **kwargs):
        found = super().get_paths_info(**kwargs)
        return [item for item in found if (kwargs["revision"], item.path) != self.omit_metadata]

    def hf_hub_download(self, **kwargs):
        assert kwargs["filename"] in {self.producer.TERMINAL, self.producer.CLAIM,
            self.producer.OUTPUT + "/" + output.MANIFEST}, "terminal observation attempted a payload body download"
        return super().hf_hub_download(**kwargs)


def test_fresh_r1_terminal_observation_is_controls_only_and_non_authorizing(tmp_path, monkeypatch, capsys):
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("terminal observation crossed a payload, execution, credential or write boundary")

    for owner, name in (
        (ci, "execute"), (ci, "verify_approval"), (ci, "verify_job_origin"), (ci, "verify_terminal"),
        (fresh, "execute"), (fresh, "_predecessor"), (fresh, "verify_terminal"), (fresh._FreshAdmission, "__init__"),
        (ci._Admission, "__init__"), (ci.LocalTransport, "github_job_token"), (ci.LocalTransport, "authority_opener"),
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
    plan = intake.registration.compile_plan()
    source = reader.reader_identity()
    assert {name: source[name] for name in reader.FROZEN} == {name: pair[1] for name, pair in reader.FROZEN.items()}
    api = TerminalHF(plan)

    def captured():
        text = capsys.readouterr()
        assert text.err == ""
        for secret in (str(tmp_path), api.repo, TOKEN, PRIVATE.decode().strip(), FILE, "SECRET-LIKE-ERROR"):
            assert secret not in text.out
        return json.loads(text.out)

    with monkeypatch.context() as inert:
        inert.setattr(retained, "_session", forbidden)
        assert reader.main([], _test_api=api) == 0
        assert captured()["read_attempted"] is False
        assert reader.main(["--read", "--observe-terminal"], _test_api=api) == 2
        assert captured()["reason"] == "invalid_arguments"
        assert reader.main(["--output", str(tmp_path / "not-opted-in")], _test_api=api) == 2
        assert captured()["reason"] == "explicit_fresh_result_read_required"
    assert api.calls == [] and not (tmp_path / "not-opted-in").exists()
    monkeypatch.setenv("HF_TOKEN", TOKEN)  # Synthetic token, scrubbed by the real retained session.

    # One coupled smoke case, not the delivered reader selector: its original
    # default success path still accepts the real schema-valid synthetic result
    # with the old synthetic job. The new job pin belongs only to observation.
    success_api = FreshResultHF(plan)
    success = reader.read_result(expectation=reader.EXPECTATION, destination=tmp_path / "success-unchanged",
        expected_reader_sha256=source["module_sha256"], terminal_revision=TERMINAL_HEAD, _test_api=success_api)
    assert success["intake_verified"] is True and success["status"] == "succeeded"
    assert success["recorded_provider_job_id"] == 123456 and "terminal_verified" not in success
    assert (tmp_path / "success-unchanged" / reader.MARKER).is_file() and success_api.commits == []

    for owner, name in ((intake, "_payload"), (intake, "validate_inference_result_fingerprint"),
                        (intake.retained_reader, "_fetch"), (output, "_ledger")):
        monkeypatch.setattr(owner, name, forbidden)

    def observe(transport, name, **changes):
        options = dict(expectation=reader.EXPECTATION, destination=tmp_path / name,
            expected_reader_sha256=source["module_sha256"], terminal_revision=TERMINAL_HEAD, _test_api=transport)
        return reader.observe_terminal(**{**options, **changes})

    def argv(name):
        return ["--observe-terminal", "--discover-terminal", "--expected-producer-source", reader.PRODUCER_SOURCE,
            "--expected-request-sha256", reader.REQUEST_SHA256, "--cell-id", fresh.CELL_ID,
            "--expected-reader-sha256", source["module_sha256"], "--output", str(tmp_path / name)]

    for index, (changes, reason) in enumerate((
        ({"expectation": object()}, "fresh_result_expectation_required"),
        ({"expectation": replace(reader.EXPECTATION, source_sha="0" * 40)}, "fresh_result_expected_producer_mismatch"),
        ({"expectation": replace(reader.EXPECTATION, request_sha256="0" * 64)}, "fresh_result_expected_request_mismatch"),
        ({"expectation": replace(reader.EXPECTATION, cell_id=intake.controller.FIRST_CELL_ID)}, "fresh_result_expected_cell_mismatch"),
        ({"expected_reader_sha256": "0" * 64}, "fresh_result_reader_bytes_mismatch"),
        ({"discover_terminal": True}, "one_terminal_revision_or_discovery_required"),
    )):
        name = "binding-" + str(index)
        with pytest.raises(output.OutputPublicationRefused) as refused:
            observe(api, name, **changes)
        assert refused.value.args == (reason,)
        assert not (tmp_path / name).exists() and api.calls == []

    null_cost = ci.project_cost_receipt(CostReceipt(status="partial", model_calls=2,
        usage={"input_tokens": 12, "cached_input_tokens": 8, "output_tokens": 3, "reasoning_tokens": 2},
        missing_reasons=("price_missing",)).as_dict())
    known_cost = ci.project_cost_receipt(CostReceipt(status="partial", known_cost_usd=Decimal("0.01"),
        model_cost_usd=Decimal("0.01"), model_calls=2, usage=null_cost["usage"],
        missing_reasons=("price_missing",)).as_dict())
    transports = []
    for index, (status, declared, receipt, exit_code) in enumerate((
        ("failed", "none", None, 137), ("stopped", "none", null_cost, None),
        ("failed", "partial", known_cost, 0), ("stopped", "result", None, -15),
    )):
        valid = TerminalHF(plan, status=status, declared=declared, receipt=receipt, exit_code=exit_code)
        transports.append(valid)
        name = "valid-" + str(index)
        # Success intake has no implicit fallback, even with declared payloads.
        with pytest.raises(output.OutputPublicationRefused) as refused:
            reader._summary(valid.summary)
        assert refused.value.args == ("fresh_result_success_required",)
        code = reader.main(argv(name), _test_api=valid)
        record = captured()
        assert code == 0, {key: record.get(key) for key in ("reason", "outcome")}
        assert record["outcome"] == "terminal_verified" and record["terminal_verified"] is True
        assert record["mode"] == "observe_terminal" and record["format"] == reader.TERMINAL_FORMAT
        assert record["status"] == status and record["exit_code"] == exit_code and record["cleanup_confirmed"] is True
        assert record["cell_id"] == fresh.CELL_ID and record["request_sha256"] == reader.REQUEST_SHA256
        assert record["producer_source_sha"] == reader.PRODUCER_SOURCE
        assert record["terminal_commit"] == TERMINAL_HEAD
        assert record["terminal_identity"] == owned._identity(valid.trees[TERMINAL_HEAD][fresh.TERMINAL])
        assert record["claim_commit"] == CLAIM_HEAD and record["claim_identity"] == owned._identity(valid.trees[CLAIM_HEAD][fresh.CLAIM])
        assert record["output_commit"] == OUTPUT_HEAD
        assert record["output_manifest_identity"] == owned._identity(valid.trees[OUTPUT_HEAD][fresh.OUTPUT + "/" + output.MANIFEST])
        assert record["output_objects_sha256"] == owned._digest(valid.terminal["output_objects"])
        assert record["retained_authority_sha256"] == owned._digest(valid.terminal["authority"])
        assert record["predecessor"] == fresh.PREDECESSOR
        assert record["expected_provider"] == reader.EXPECTED_PROVIDER
        assert record["expected_execution_job_id"] == record["recorded_provider_job_id"] == 110323708382
        assert record["recorded_provider_run_id"] == reader.RUN_ID
        assert record["supplied_request_binding"] == reader.SUPPLIED_REQUEST_BINDING
        assert record["declared_payload_roles"] == {"inference_result": int(declared != "none"),
            "ledger": int(declared == "partial"), "deliverables": int(declared == "partial")}
        assert record["declared_output_object_count"] == len(valid.files) + 1
        assert record["receipt"] == receipt and record["accounting"] == valid.summary["accounting"]
        assert record["missing"] == valid.summary["missing"] and record["http_request_count"] is None
        assert record["proof"] == "verified_publication_derived_not_independent_provider_authentication"
        assert record["writer_acknowledgment"] == "not_established" and record["recorded_publication_acknowledged"] is True
        assert record["unavailable"] == {field: {"status": "unavailable", "value": None,
            "reason": "not_recorded_in_terminal_controls"} for field in ("detailed_failure", "budget", "recovery_exposure")}
        for field in ("payload_bodies_verified", "grading_input_ready", "fresh_origin_authentication",
                      "prepared_input_independently_verified", "git_parent_cas_independently_verified",
                      "launch_authorized", "admission_attempted", "replay_authorized", "grading_launched", "invoice_complete"):
            assert record[field] is False
        assert record["grade"] is None and record["commands"] == []
        assert not {"intake_verified", "judge_ready", "files", "result"} & set(record)
        marker = tmp_path / name / reader.TERMINAL_MARKER
        saved = marker.read_bytes()
        assert record["observation_sha256"] == owned._identity(saved)["sha256"]
        assert not {"terminal_verified", "outcome", "intake_verified", "judge_ready"} & set(json.loads(saved))
        assert marker.stat().st_mode & 0o077 == 0 and (tmp_path / name).stat().st_mode & 0o077 == 0
        assert not (tmp_path / name / reader.MARKER).exists()
        assert not (tmp_path / name / intake.CACHE / "payloads").exists()
        assert all(not (tmp_path / name / file).exists() for file in valid.files)
        assert valid.downloads == [(TERMINAL_HEAD, fresh.TERMINAL), (CLAIM_HEAD, fresh.CLAIM),
                                   (OUTPUT_HEAD, fresh.OUTPUT + "/" + output.MANIFEST)]
        assert valid.path_reads[0] == (retained.BRANCH, (fresh.TERMINAL,))
        assert all(revision in {TERMINAL_HEAD, CLAIM_HEAD, OUTPUT_HEAD} for revision, _ in valid.path_reads[1:])
        assert valid.commits == [] and effects == []
    assert all(null_cost[field] is None for field in ("known_cost_usd", "model_cost_usd", "estimated_cost_usd", "runtime_cost_usd"))
    assert known_cost["known_cost_usd"] == 0.01 and known_cost["estimated_cost_usd"] is None
    assert known_cost["model_calls"] == 2 and known_cost["usage"] == null_cost["usage"]

    missing = TerminalHF(plan)
    del missing.trees[missing.head][fresh.TERMINAL]
    assert reader.main(argv("missing-terminal"), _test_api=missing) == 2
    assert captured()["reason"] == "fresh_result_terminal_not_ready"
    assert missing.downloads == [] and missing.path_reads == [(retained.BRANCH, (fresh.TERMINAL,))]

    reasons = {
        "source": "fresh_result_completion_mismatch", "cell": "fresh_result_completion_mismatch",
        "request": "fresh_result_terminal_binding_mismatch", "run": "fresh_result_authority_binding_mismatch",
        "job": "fresh_terminal_execution_job_mismatch", "job-bool": "fresh_result_authority_binding_mismatch",
        "claim": "fresh_result_terminal_claim_mismatch", "claim-number": "fresh_result_terminal_claim_mismatch",
        "predecessor": "fresh_result_predecessor_mismatch", "predecessor-number": "fresh_result_predecessor_mismatch",
        "parent": "fresh_result_predecessor_mismatch", "cleanup": "fresh_result_completion_mismatch",
        "grade-zero": "fresh_result_completion_mismatch", "grading": "fresh_result_completion_mismatch",
        "invoice": "fresh_result_completion_mismatch", "success": "fresh_terminal_unsuccessful_required",
        "unfinished": "fresh_terminal_unsuccessful_required", "exit-bool": "fresh_terminal_unsuccessful_required",
        "exit-float": "fresh_terminal_unsuccessful_required", "no-result-with-files": "fresh_terminal_missing_result_roles",
        "missing-fields": "fresh_result_missing_accounting_mismatch", "receipt-number": "fresh_result_accounting_mismatch",
        "unacknowledged": "fresh_result_terminal_binding_mismatch", "private-role": "retention_result_private_state_refused",
        "sqlite-role": "retention_result_private_state_refused", "claim-hash": "payload_identity_mismatch",
        "terminal-bytes": "retention_control_blob_mismatch", "manifest-bytes": "retention_control_blob_mismatch",
        "history": "remote_output_history_mismatch", "claim-history": "retention_control_history_mismatch",
        "terminal-history": "retention_control_history_mismatch", "extra-object": "fresh_result_output_objects_mismatch",
        "object-hash": "fresh_result_output_objects_mismatch", "object-body": "remote_output_blob_mismatch",
        "summary-bool": "fresh_result_summary_readback_mismatch", "noncanonical": "noncanonical_retention_record",
        "control-bound": "retention_control_file_refused", "missing-claim": "terminal_or_claim_missing",
        "missing-manifest": "terminal_or_claim_missing", "missing-object": "remote_output_objects_missing",
    }
    for mode, reason in reasons.items():
        bad = TerminalHF(plan)
        if mode in {"source", "cell"}:
            bad.summary[{"source": "source_sha", "cell": "cell_id"}[mode]] = "wrong-binding"
        elif mode == "request":
            bad.terminal["request_sha256"] = "0" * 64
        elif mode in {"run", "job", "job-bool"}:
            for authority in (bad.claim["authority"], bad.terminal["authority"]):
                if mode == "run":
                    authority["provider_run_id"] = intake.RUN_ID
                else:
                    authority["provider_job_id"] = True if mode == "job-bool" else 123456
        elif mode == "claim":
            bad.claim["request_sha256"] = "0" * 64
        elif mode == "claim-number":
            bad.claim["authority"]["provider_job_id"] = float(reader.EXPECTED_EXECUTION_JOB_ID)
        elif mode == "predecessor":
            bad.claim["predecessor"]["output_commit"] = "0" * 40
        elif mode == "predecessor-number":
            identity = bad.claim["predecessor"]["terminal_identity"]
            identity["size"] = float(identity["size"])
        elif mode == "parent":
            bad.claim["expected_parent"] = "0" * 40
        elif mode in {"cleanup", "grade-zero", "grading", "invoice", "success", "unfinished", "exit-bool", "exit-float"}:
            field, value = {"cleanup": ("cleanup_confirmed", 1), "grade-zero": ("grade", 0),
                "grading": ("grading_launched", 0), "invoice": ("invoice_complete", True),
                "success": ("status", "succeeded"), "unfinished": ("status", "running"),
                "exit-bool": ("exit_code", True), "exit-float": ("exit_code", 137.0)}[mode]
            bad.summary[field] = value
        elif mode == "no-result-with-files":
            del bad.files[intake.RESULT]
        elif mode == "missing-fields":
            bad.summary["missing"] = []
        elif mode == "receipt-number":
            bad.summary.update(receipt=deepcopy(known_cost), accounting="partial")
            bad.summary["receipt"]["known_cost_usd"] = 1  # Projector normalizes to 1.0; canonical bytes must match.
        elif mode == "unacknowledged":
            bad.terminal["publication_acknowledged"] = False
        elif mode == "private-role":
            bad.files[FILE.rsplit("/", 1)[0] + "/HOME/auth.json"] = PRIVATE
        elif mode == "sqlite-role":
            bad.files[FILE.rsplit("/", 1)[0] + "/native.db"] = PRIVATE
        elif mode in {"terminal-bytes", "manifest-bytes"}:
            bad.corrupt = fresh.TERMINAL if mode == "terminal-bytes" else fresh.OUTPUT + "/" + output.MANIFEST
        bad.seed()
        if mode == "claim-hash":
            bad.terminal["claim_identity"]["sha256"] = "0" * 64
        elif mode == "extra-object":
            bad.terminal["output_objects"].append(deepcopy(bad.terminal["output_objects"][0]))
        elif mode == "object-hash":
            bad.terminal["output_objects"][0]["sha256"] = "0" * 64
        elif mode == "object-body":
            bad.trees[TERMINAL_HEAD][fresh.OUTPUT + "/" + FILE] = b"X" * len(PRIVATE)
        elif mode == "history":
            bad.writers[TERMINAL_HEAD][fresh.OUTPUT + "/" + FILE] = TERMINAL_HEAD
        elif mode == "claim-history":
            bad.writers[CLAIM_HEAD][fresh.CLAIM] = TERMINAL_HEAD
        elif mode == "terminal-history":
            bad.writers[TERMINAL_HEAD][fresh.TERMINAL] = OUTPUT_HEAD
        elif mode == "summary-bool":
            altered = deepcopy(bad.summary)
            altered["cleanup_confirmed"] = 1
            path, data = fresh.OUTPUT + "/" + output.MANIFEST, retained._encoded(altered)
            for head in (OUTPUT_HEAD, TERMINAL_HEAD):
                bad.trees[head][path] = data
            bad.terminal["output_objects"] = [retained._object(path, data) if item["path"] == path else item
                                              for item in bad.terminal["output_objects"]]
        elif mode in {"missing-claim", "missing-manifest", "missing-object"}:
            bad.omit_metadata = {"missing-claim": (CLAIM_HEAD, fresh.CLAIM),
                "missing-manifest": (OUTPUT_HEAD, fresh.OUTPUT + "/" + output.MANIFEST),
                "missing-object": (TERMINAL_HEAD, fresh.OUTPUT + "/" + FILE)}[mode]
        bad.trees[TERMINAL_HEAD][fresh.TERMINAL] = retained._encoded(bad.terminal)
        if mode == "noncanonical":
            bad.trees[TERMINAL_HEAD][fresh.TERMINAL] = json.dumps(bad.terminal, indent=2).encode()
        elif mode == "control-bound":
            bad.trees[TERMINAL_HEAD][fresh.TERMINAL] = b"X" * (output.MAX_MANIFEST_BYTES + 1)
        with pytest.raises(output.OutputPublicationRefused) as refused:
            observe(bad, "negative-" + mode)
        assert refused.value.args == (reason,), mode
        assert not (tmp_path / ("negative-" + mode) / reader.TERMINAL_MARKER).exists()
        assert {name for _, name in bad.downloads} <= CONTROLS and bad.commits == [] and effects == []

    # Real record/path bounds without large payload downloads or allocations.
    for mode, reason in (("duplicate", "fresh_result_output_bounds_exceeded"),
                         ("count", "fresh_result_output_bounds_exceeded"),
                         ("total", "fresh_result_output_bounds_exceeded"),
                         ("size", "fresh_result_output_identity_refused"),
                         ("size-bool", "fresh_result_output_identity_refused"),
                         ("extra-field", "fresh_result_output_identity_refused"),
                         ("record", "retention_result_record_bounds_exceeded")):
        summary = deepcopy(api.summary)
        if mode == "duplicate":
            summary["files"].append(deepcopy(summary["files"][0]))
        elif mode == "count":
            summary["files"] *= output.MAX_FILES
        elif mode == "total":
            summary["files"] = [{"path": f"deliverable_files/{intake.registration.TASK4}/{index}.txt",
                "size": output.MAX_FILE_BYTES, "sha256": "0" * 64} for index in range(3)]
        elif mode in {"size", "size-bool"}:
            summary["files"][0]["size"] = True if mode == "size-bool" else output.MAX_FILE_BYTES + 1
        elif mode == "extra-field":
            summary["files"][0]["unsafe"] = "SECRET-LIKE-ERROR"
        else:
            next(item for item in summary["files"] if item["path"] == intake.RESULT)["size"] = output.MAX_RECORD_BYTES + 1
        with pytest.raises(output.OutputPublicationRefused) as refused:
            reader._terminal_summary(summary)
        assert refused.value.args == (reason,), mode
    for path in ("unrelated.json", "../escape", FILE.replace(intake.registration.TASK4, "foreign-task")):
        summary = deepcopy(api.summary)
        summary["files"] = sorted([*summary["files"], {"path": path, "size": 1, "sha256": "0" * 64}], key=lambda item: item["path"])
        with pytest.raises(ValueError) as refused:
            reader._terminal_summary(summary)
        assert type(refused.value) is ValueError  # No raw path-bearing exception text.

    before = list(transports[0].calls)
    with pytest.raises(output.OutputPublicationRefused) as refused:
        observe(transports[0], "valid-0")
    assert refused.value.args == ("new_result_destination_required",) and transports[0].calls == before
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "unchanged"
    sentinel.write_bytes(b"UNCHANGED")
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        observe(transports[0], "symlink", destination=link / "must-not-exist")
    assert transports[0].calls == before and sentinel.read_bytes() == b"UNCHANGED"
    assert not (outside / "must-not-exist").exists()

    real_fsync = reader.os.fsync
    ambiguous = tmp_path / "ambiguous" / reader.TERMINAL_MARKER

    def fail_after_marker(descriptor):
        if ambiguous.exists():
            raise OSError("SECRET-LIKE-ERROR")
        return real_fsync(descriptor)

    with monkeypatch.context() as publication:
        publication.setattr(reader.os, "fsync", fail_after_marker)
        assert reader.main(argv("ambiguous"), _test_api=TerminalHF(plan)) == 2
    refusal = captured()
    assert refusal["reason"] == "fresh_terminal_observation_unconfirmed" and refusal["terminal_verified"] is False
    assert not {"terminal_verified", "outcome", "intake_verified", "judge_ready"} & set(json.loads(ambiguous.read_bytes()))
    assert reader.main(argv("ambiguous"), _test_api=TerminalHF(plan)) == 2
    assert captured()["reason"] == "fresh_terminal_observation_refused"
    secret_error = TerminalHF(plan)
    secret_error.read_error = ValueError("SECRET-LIKE-ERROR")
    assert reader.main(argv("redacted-error"), _test_api=secret_error) == 2
    refusal = captured()
    assert refusal["reason"] == "fresh_terminal_observation_refused" and refusal["terminal_verified"] is False
    assert secret_error.downloads == [] and effects == []
    assert all(transport.commits == [] for transport in transports)
