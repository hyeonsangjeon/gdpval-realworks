"""One offline fixed-reader proof; no running producer or real result is read."""

import builtins
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
from types import SimpleNamespace

import pytest
import yaml

import codex_retention_fresh_r1_result_intake as reader
import codex_retention_grade_readout as observer
import codex_retention_task5_keep_r1 as producer
import gpt54_disposable_checkout as source_checkout
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from core.cost_receipts import CostReceipt
from core.reference_integrity import ReferenceIntegrityError
from .test_codex_budget_pilot_retention import TOKEN, offline  # noqa: F401
# This module captures real Popen methods: resolve it at collection, not after
# the autouse offline fixture has replaced all process constructors.
from .test_codex_retention_ci import REAL_POPEN
from . import test_codex_retention_ci_observation as workflow_contract
from .test_codex_retention_result_intake import CLAIM_HEAD, OUTPUT_HEAD, TERMINAL_HEAD, FILE, PRIVATE
from .test_codex_retention_task5_fresh_r1_read import _task5_fixture, TASK5_FILE

ci, retained, output, owned, intake = reader.ci, reader.retained, reader.output, reader.owned, reader.intake


def test_task5_keep_r1_reader_is_fixed_model_free_and_closed(tmp_path, monkeypatch, capsys):
    effects, transports, errors = [], [], []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("fixed reader crossed a writer, child, model or authority boundary")

    for owner, names in (
        (ci, ("execute", "verify_approval", "verify_job_origin", "verify_terminal")),
        (producer, ("execute", "_predecessor", "verify_terminal")),
        (producer._Task5KeepR1Admission, ("__init__",)), (ci._Admission, ("__init__",)),
        (ci.LocalTransport, ("github_job_token", "authority_opener", "github", "azure")),
        (owned.LocalTransport, ("clock", "child", "process")),
        (ci.preparation, ("prepare_packet", "verify_packet")), (ci.historical, ("observe",)),
        (ci.controller, ("execute_first_cell", "stage_runtime", "_deadline")),
        (CodexTaskDeadlineStore, ("__init__",)), (CodexTaskDeadline, ("admit_attempt",)),
        (intake.retained_reader, ("prepare", "main")), (output, ("_hf_client", "publish")),
        (reader.fresh, ("_finish_publication",)),
        (observer.bridge, ("prepare", "claim", "judge", "publish", "reconcile")),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    assert subprocess.Popen is not REAL_POPEN and subprocess.Popen.__name__ == "blocked"

    def observed(function):
        def call(**kwargs):
            try:
                return function(**kwargs)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, AssertionError) as error:
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
                raise  # No strings, bodies, credentials or private paths in diagnostics.
        return call

    monkeypatch.setattr(reader, "read_result", observed(reader.read_result))
    monkeypatch.setattr(reader, "observe_terminal", observed(reader.observe_terminal))
    binding = reader.TASK5_KEEP_R1
    assert binding.expectation == ci.TerminalExpectation(
        "22e0bc6f06e4c9c2ac2d3fa4bfe6a7c567ef24e9111bf319b704409d731997de",
        "a8353cd41f01f7d94129421512a57a62b9bd6997",
        "0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_keep_r1")
    assert (binding.ordinal, binding.repetition, binding.retention_bundle, binding.run_id,
            binding.execution_job_id) == (5, 1, "keep", "37066171719", 111036410671)
    assert reader._request_context(binding) == {
        "original_input_bundle_sha256": "757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3",
        "materialized_grader_source_sha256": None}
    assert producer.PREDECESSOR["terminal_commit"] == "94628d12162da2e00cace216fdda5ce41f57e47f"
    assert producer.PREDECESSOR["terminal_identity"] == {
        "sha256": "5bc2eb37dd4ab83cd7653106166cc18d36c193eec12e2bc99b9bf429be6942cf", "size": 4188}
    source = reader.reader_identity(binding=binding)
    assert source["producer_task5_keep_r1_sha256"] == "21623a1a5bb661f105b8d9dcdfaaad13634c21cb8f1207189608f602b80b14ee"
    assert reader.reader_identity(binding=reader.TASK5_FRESH_R1) == {
        key: value for key, value in source.items() if key != "producer_task5_keep_r1_sha256"}
    plan = intake.registration.compile_plan()

    def make(*, terminal=False, **options):
        api = _task5_fixture(plan, binding=binding, terminal=terminal, **options)
        for name in ("create_commit", "repo_info", "list_repo_tree"):
            monkeypatch.setattr(api, name, forbidden)
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
            ({"binding": replace(binding, ordinal=6)}, "fixed_fresh_read_binding_required"),
            ({"expectation": replace(binding.expectation, cell_id=reader.TASK5_FRESH_R1.expectation.cell_id)}, "fresh_result_expected_cell_mismatch"),
            ({"expectation": replace(binding.expectation, source_sha=reader.TASK5_FRESH_R1.expectation.source_sha)}, "fresh_result_expected_producer_mismatch"),
            ({"expectation": replace(binding.expectation, request_sha256=reader.TASK5_FRESH_R1.expectation.request_sha256)}, "fresh_result_expected_request_mismatch"),
            ({"expected_reader_sha256": "d14673345ed406c1f2054d55ee38209f28aa8862d7bd324d88ceeb36dd649e53"}, "fresh_result_reader_bytes_mismatch"),
            ({"discover_terminal": True}, "one_terminal_revision_or_discovery_required"),
        )):
            for terminal in (False, True):
                name = f"early-{index}-{terminal}"
                refuse(api, name, reason, terminal=terminal, **changes)
                assert not (tmp_path / name).exists()
        wrong = deepcopy(plan)
        wrong["cells"][5]["control"]["retention_bundle"] = "fresh"
        early.setattr(intake.registration, "compile_plan", lambda: wrong)
        refuse(api, "wrong-treatment", "fresh_result_registered_cell_mismatch")
    assert not api.calls and not effects

    real_bytes, real_import = output._bytes, builtins.__import__
    for bad_path, _ in reader._frozen(binding).values():
        def changed_bytes(path, **kwargs):
            data = real_bytes(path, **kwargs)
            return data + b"\n" if Path(path) == Path(bad_path) else data

        def no_lazy_import(name, *args, **kwargs):
            if name == "codex_retention_task5_keep_r1":
                return forbidden()
            return real_import(name, *args, **kwargs)

        with monkeypatch.context() as corrupt:
            corrupt.setattr(output, "_bytes", changed_bytes)
            corrupt.setattr(builtins, "__import__", no_lazy_import)
            corrupt.setattr(retained, "_session", forbidden)
            refuse(api, "bytes-" + Path(bad_path).stem, "fresh_result_reader_bytes_mismatch")
            if Path(bad_path) == reader.TASK5_KEEP_PRODUCER_PIN[0]:
                with pytest.raises(output.OutputPublicationRefused, match="^fresh_result_reader_bytes_mismatch$"):
                    reader._producer(binding)
    assert not api.calls and not effects

    monkeypatch.setenv("HF_TOKEN", TOKEN)  # Synthetic transport, not a credential.
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
    assert success["result"]["registered_config_sha256"] == plan["cells"][5]["config_sha256"]
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
    for transport, record in evidence:
        assert record["ordinal"] == 5 and record["cell_id"] == binding.expectation.cell_id
        assert record["producer_source_sha"] == binding.expectation.source_sha
        assert record["request_sha256"] == binding.expectation.request_sha256
        assert record["recorded_provider_job_id"] == record["expected_execution_job_id"] == 111036410671
        assert record["recorded_provider_run_id"] == record["expected_provider"]["run_id"] == "37066171719"
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
        for job in (reader.TASK5_FRESH_R1.execution_job_id, True, float(binding.execution_job_id)):
            bad = make(terminal=terminal)
            for authority in (bad.claim["authority"], bad.terminal["authority"]):
                authority["provider_job_id"] = job
            bad.seed()
            reason = "fresh_terminal_execution_job_mismatch" if terminal else "fresh_result_execution_job_mismatch"
            refuse(bad, f"job-{terminal}-{job}", reason if type(job) is int else
                   "fresh_result_authority_binding_mismatch", terminal=terminal)
        for fault, reason in (("source", "fresh_result_completion_mismatch"), ("cell", "fresh_result_completion_mismatch"),
            ("request", "fresh_result_terminal_binding_mismatch"), ("run", "fresh_result_authority_binding_mismatch"),
            ("cleanup", "fresh_result_completion_mismatch"), ("grade", "fresh_result_completion_mismatch"),
            ("parent-grade", "fresh_result_predecessor_mismatch"), ("parent-task4", "fresh_result_predecessor_mismatch"),
            ("predecessor", "fresh_result_predecessor_mismatch")):
            bad = make(terminal=terminal)
            if fault in {"source", "cell", "cleanup", "grade"}:
                key, value = {"source": ("source_sha", reader.TASK5_FRESH_R1.expectation.source_sha),
                    "cell": ("cell_id", reader.TASK5_FRESH_R1.expectation.cell_id), "cleanup": ("cleanup_confirmed", 1),
                    "grade": ("grade", 0)}[fault]
                bad.summary[key] = value
            elif fault == "request":
                bad.terminal["request_sha256"] = reader.TASK5_FRESH_R1.expectation.request_sha256
            elif fault == "run":
                for authority in (bad.claim["authority"], bad.terminal["authority"]):
                    authority["provider_run_id"] = reader.TASK5_FRESH_R1.run_id
            elif fault == "predecessor":
                bad.claim["predecessor"]["execution_job_id"] = float(producer.PREDECESSOR["execution_job_id"])
            else:
                bad.claim["expected_parent"] = ("76f51d0464b3c90d9ff80b78b656b9e7d45a0b6e" if fault == "parent-grade"
                                                else "e55fac5d60191167dd66688510ec0fef472e594d")
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
        existing = tmp_path / name / (binding.terminal_marker if terminal else binding.result_marker)
        saved = existing.read_bytes()
        with pytest.raises(output.OutputPublicationRefused, match="^new_result_destination_required$"):
            read(api, name, terminal=terminal)
        assert existing.read_bytes() == saved
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

    # Source-only compatibility checks, not replays of any old delivered suite.
    fixed_readers = (reader.FRESH_R1, reader.FRESH_R2, reader.KEEP_R2, reader.TASK5_FRESH_R1,
                     binding, reader.TASK5_KEEP_R2, reader.TASK5_FRESH_R2)
    assert reader.FRESH_R1.expectation is reader.EXPECTATION
    for old in fixed_readers:
        checked, registered, cell = reader._binding(old.expectation, source["module_sha256"], TERMINAL_HEAD, False,
            **({} if old is reader.FRESH_R1 else {"binding": old}))
        assert cell["index"] == old.ordinal and registered["order"][old.ordinal] == old.expectation.cell_id
        assert {name: checked[name] for name in reader._frozen(old)} == {
            name: pin[1] for name, pin in reader._frozen(old).items()}
    assert reader.TASK5_FRESH_R1.materialized_grader_source_sha256 == "a820cd9e3a8e74e684aa65a710e5a7b0649ce0435fe425a070a0eb6d8b30145e"
    bridge = observer.bridge
    historical_adapter = bridge._fixed("retention/keep-r2")
    historical = deepcopy((bridge.RESULT, bridge.PARENT, bridge.READER,
        historical_adapter.RESULT, historical_adapter.PARENT, historical_adapter.READER))
    assert bridge.fixed_evidence_sha256() == "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d"
    assert bridge.fixed_evidence_sha256(historical_adapter.SELECTOR) == "25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0"
    assert historical_adapter.RESULT["intake_sha256"] == "4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4"
    assert historical_adapter.READER["module_sha256"] == "5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583"
    assert observer.CURRENT_DEPENDENCIES["codex_retention_fresh_r1_result_intake.py"] == source["module_sha256"]
    for name, digest in observer.CURRENT_DEPENDENCIES.items():
        assert hashlib.sha256((bridge.ROOT / "batch-runner" / name).read_bytes()).hexdigest() == digest
    common = tmp_path / "git-common"
    common.mkdir()
    expected = "a" * 40  # Synthetic exact-checkout identity, never provider evidence.
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
        assert command in answers  # Only transport is synthetic; checkout/hash guards are real.
        return SimpleNamespace(stdout=answers[command], returncode=0)

    with monkeypatch.context() as current:
        current.setattr(source_checkout, "_git", git)
        current.setattr(owned, "_git", git)
        current.setattr(retained, "_session", forbidden)
        current.setattr(observer.grade, "_root", forbidden)
        for selector in (observer.SELECTOR, observer.KEEP_R2_SELECTOR):
            observer._source_current(expected, selector=selector)
        with pytest.raises(output.OutputPublicationRefused, match="^reviewed_retention_reader_required$"):
            bridge._source(bridge.compile_request(expected, selector=historical_adapter.SELECTOR))
        for missing in (False, True):
            def changed_current(path, **kwargs):
                if Path(path) == Path(reader.__file__):
                    if missing:
                        raise FileNotFoundError("synthetic missing dependency")
                    return real_bytes(path, **kwargs) + b"\n"
                return real_bytes(path, **kwargs)

            with monkeypatch.context() as changed:
                changed.setattr(output, "_bytes", changed_current)
                if missing:
                    with pytest.raises(FileNotFoundError):
                        observer._source_current(expected, selector=observer.KEEP_R2_SELECTOR)
                else:
                    with pytest.raises(output.OutputPublicationRefused, match="^reviewed_retention_observer_dependency_required$"):
                        observer._source_current(expected, selector=observer.KEEP_R2_SELECTOR)
        for key, value, reason in (("head", "e" * 40, "retention_grade_source_changed"),
            ("diff", b"tracked.py\n", "retention_grade_source_changed"),
            ("status", b"?? untracked.py\n", "clean_retention_grade_source_required"),
            ("config", b"include.path\n", "checkout filters, includes or partial-clone configuration are unsupported")):
            before = state[key]
            state[key] = value
            with pytest.raises(ValueError, match="^" + reason + "$"):
                observer._source_current(expected, selector=observer.KEEP_R2_SELECTOR)
            state[key] = before
    assert historical == (bridge.RESULT, bridge.PARENT, bridge.READER,
        historical_adapter.RESULT, historical_adapter.PARENT, historical_adapter.READER)

    # Pure assertion helpers were imported at collection; guards stay active.
    assert subprocess.Popen is not REAL_POPEN and subprocess.Popen.__name__ == "blocked"
    workflow_contract._assert_retention_execution_workflow_contract()
    workflow_contract._assert_retention_mode_routes()  # 576 exact mode/cell cases.
    workflow = yaml.safe_load((ci.ROOT / ci.WORKFLOW).read_bytes())
    steps = workflow["jobs"][ci.PREPARE_JOB]["steps"]
    read_group = " && (" + " || ".join("inputs.cell_id == '" + fixed.expectation.cell_id + "'"
                                      for fixed in fixed_readers) + ")"
    assert steps[9]["if"] == steps[10]["if"] == (
        "inputs.read_result && !inputs.observe_terminal && !inputs.observe_budget && !inputs.prepare && !inputs.execute && !inputs.observe_locator" + read_group)
    assert steps[13]["if"] == steps[14]["if"] == (
        workflow_contract._terminal_observation_condition() + read_group)
    assert steps[13]["run"] == steps[9]["run"] + (
        'if [[ "$OBSERVE_BUDGET_ONLY" == true ]]; then\n'
        "  printf '%s\\n' '" + reader.BUDGET_PROJECTOR_PIN[1] + "  batch-runner/codex_budget_pilot_grade_readout.py' | sha256sum --check --status\nfi\n")
    expected_pins = {"batch-runner/" + Path(path).name: digest
                     for path, digest in reader._frozen(reader.TASK5_FRESH_R2).values()}
    expected_pins["batch-runner/" + Path(reader.__file__).name] = source["module_sha256"]
    for index, mode in ((9, "--read"), (13, "--observe-terminal")):
        preflight, read_step = steps[index:index + 2]
        assert preflight.get("env", {}) == ({} if index == 9 else {"OBSERVE_BUDGET_ONLY": "${{ inputs.observe_budget }}"})
        assert "secrets." not in preflight["run"]
        assert '"$(git rev-parse HEAD)" == "$REVIEWED_SOURCE_SHA"' in preflight["run"]
        assert "git status --porcelain=v1 --untracked-files=all" in preflight["run"]
        pins = re.findall(r"'([0-9a-f]{64})  (batch-runner/[^']+)'", preflight["run"])
        expected = {**expected_pins, **({} if index == 9 else {
            "batch-runner/codex_budget_pilot_grade_readout.py": reader.BUDGET_PROJECTOR_PIN[1]})}
        assert len(pins) == len(expected) and {path: digest for digest, path in pins} == expected
        for digest, path in pins:
            assert hashlib.sha256((ci.ROOT / path).read_bytes()).hexdigest() == digest
        assert preflight["run"].count("sha256sum --check --status") == (7 if index == 9 else 8)
        assert read_step["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}", **({} if index == 9 else {
            "OBSERVE_BUDGET_ONLY": "${{ inputs.observe_budget }}"})} and read_step["timeout-minutes"] == 4
        expected_case = (binding.expectation.cell_id + ")\n"
            "    retention_read_source=" + binding.expectation.source_sha + "\n"
            "    retention_read_request=" + binding.expectation.request_sha256 + "\n"
            "    retention_read_namespace=retention-task5-keep-r1 ;;")
        assert expected_case in read_step["run"] and "*) exit 2 ;;" in read_step["run"]
        command = shlex.split(next(line for line in read_step["run"].replace("\\\n", "").splitlines()
                                  if line.startswith("env -u ")))
        assert command[:16] == ["env", "-u", "GITHUB_TOKEN", "-u", "GH_TOKEN", "-u", "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
            "-u", "ACTIONS_ID_TOKEN_REQUEST_URL", "-u", "ACTIONS_RUNTIME_TOKEN", "timeout", "--signal=KILL", "180s",
            "python3", "batch-runner/codex_retention_fresh_r1_result_intake.py"]
        assert command[16:18] == ([mode, "--discover-terminal"] if index == 9 else ["${retention_terminal_args[@]}", "--expected-producer-source"])
        if index == 13:
            assert "retention_terminal_args=(--observe-terminal --discover-terminal)" in read_step["run"]
        assert command[command.index("--expected-reader-sha256") + 1] == source["module_sha256"]
        assert "stderr.log" not in read_step["run"].split("# Only the reviewed reader")[1]
    assert not effects and all(not api.commits for api in transports)
    print(json.dumps({"scope": "synthetic_task5_keep_r1_fixed_reader", "success_payload_verified": True,
        "failed_stopped_three_controls_only": True, "identity_history_payload_refusals": True,
        "marker_no_clobber_unresolved_ack": True, "current_source_historical_evidence_separated": True,
        "old_defaults_preserved": True, "mode_cases": 576, "live_effects": len(effects)}, sort_keys=True))
