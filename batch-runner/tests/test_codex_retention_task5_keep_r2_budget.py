"""One offline proof of the paired KEEP budget extension, never a live read."""

import builtins
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import hashlib
import itertools
import json
from pathlib import Path
import re
import shlex
import socket
import subprocess

import pytest
import yaml

import codex_retention_fresh_r1_result_intake as reader
import codex_retention_grade_readout as observer
import codex_retention_task5_keep_r2 as producer
import codex_retention_task5_fresh_r2 as fresh_producer
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from core.cost_receipts import CostReceipt
from .test_codex_budget_pilot_retention import TOKEN, offline  # noqa: F401
# Import pure helpers before the autouse fixture replaces Popen.
from .test_codex_retention_ci import REAL_POPEN
from . import test_codex_retention_ci_observation as workflow_contract
from . import test_codex_retention_fresh_r1_result_intake as fixtures
from .test_codex_retention_task5_fresh_r1_read import _task5_fixture, TASK5_FILE
from .test_codex_retention_result_intake import PRIVATE

ci, retained, output, owned, intake = reader.ci, reader.retained, reader.output, reader.owned, reader.intake


def _recorded_controls(row):
    return {
        "terminal_commit": row["terminal"]["revision"],
        "terminal_identity": {"sha256": row["terminal"]["sha256"], "size": row["terminal"]["bytes"]},
        "claim_commit": row["claim"]["revision"],
        "claim_identity": {"sha256": row["claim"]["sha256"], "size": row["claim"]["bytes"]},
        "output_commit": row["output_manifest"]["revision"],
        "output_manifest_identity": {"sha256": row["output_manifest"]["sha256"], "size": row["output_manifest"]["bytes"]},
        "output_objects_sha256": row["output_objects_sha256"],
        "retained_authority_sha256": row["read"]["retained_authority_sha256"],
        **{key: row[key] for key in ("status", "exit_code", "cleanup_confirmed")},
    }


def test_paired_task5_keep_r2_budget_is_fixed_private_and_model_free(tmp_path, monkeypatch, capsys):
    effects, transports, failures = [], [], []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("paired budget observation crossed a network, model, writer, child or paid boundary")

    for owner, names in (
        (ci, ("execute", "verify_approval", "verify_job_origin", "verify_terminal")),
        (producer, ("execute", "_predecessor", "verify_terminal")),
        (fresh_producer, ("execute", "_predecessor", "verify_terminal")),
        (producer._Task5KeepR2Admission, ("__init__",)), (fresh_producer._Task5FreshR2Admission, ("__init__",)),
        (ci._Admission, ("__init__",)),
        (ci.LocalTransport, ("github_job_token", "authority_opener", "github", "azure")),
        (owned.LocalTransport, ("clock", "child", "process")),
        (ci.preparation, ("prepare_packet", "verify_packet")), (ci.historical, ("observe",)),
        (ci.controller, ("execute_first_cell", "stage_runtime", "_deadline")),
        (CodexTaskDeadlineStore, ("__init__",)), (CodexTaskDeadline, ("admit_attempt",)),
        (intake.retained_reader, ("prepare", "main")), (output, ("_hf_client", "publish")),
        (observer.bridge, ("prepare", "claim", "judge", "publish", "reconcile")),
        (observer.readout, ("main",)), (fixtures.FreshResultHF, ("create_commit", "list_repo_tree")),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    assert subprocess.Popen is not REAL_POPEN and subprocess.Popen.__name__ == "blocked"
    assert socket.create_connection.__name__ == socket.socket.connect.__name__ == "blocked"

    # Retain original exception classes and relative frames if CLI redaction
    # hides a new assertion's cause. Never include private messages or paths.
    real_observe = reader.observe_terminal

    def observed(**kwargs):
        try:
            return real_observe(**kwargs)
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
            failures.append(chain)
            raise

    monkeypatch.setattr(reader, "observe_terminal", observed)
    binding = reader.TASK5_KEEP_R2
    fixed = deepcopy(reader.TASK5_KEEP_R2_BUDGET_CONTROLS)
    fresh_fixed = deepcopy(reader.TASK5_FRESH_R2_BUDGET_CONTROLS)
    readout = json.loads((ci.ROOT / "tasks/codex_budget_pilot/retention_diagnostic_readout.json").read_bytes())
    row, fresh_row = readout["cells"][6:8]
    assert binding.expectation == ci.TerminalExpectation(
        "1b042b77fcc80b8c1a1c21fdd73feeefbcb80ce7f505b7c842aba496419386ac",
        "bdb7c21111a4c86136b6158f4969a39a9950acb3",
        "0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_keep_r2")
    assert (binding.ordinal, binding.repetition, binding.retention_bundle, binding.run_id,
            binding.execution_job_id) == (6, 2, "keep", "37081963299", 111085094584)
    assert row["producer"] == {**row["producer"], "source_sha": binding.expectation.source_sha,
        "run_id": binding.run_id, "attempt": 1, "execution_job_id": binding.execution_job_id,
        "request_sha256": binding.expectation.request_sha256, "workflow_id": 370228282}
    assert fixed == _recorded_controls(row) and fresh_fixed == _recorded_controls(fresh_row)
    assert producer.PREDECESSOR["terminal_commit"] == row["preceding_registered_inference_terminal"] == (
        "33278d9c26e8c8e8cfe68649e482e01f684d7705")
    assert binding.materialized_grader_source_sha256 == row["supplied_materialized_grader_source_sha256"]
    assert reader.TASK5_KEEP_R1.materialized_grader_source_sha256 is None
    assert row["current_budget_observation"]["mode"] == "observe_budget"

    # All six later leader-supplied receipts are separate from the original rows.
    # Removing only those fields must reproduce the canonical historical JSON.
    prior = deepcopy(readout)
    for index in (1, 2, 4, 5, 6):
        prior["cells"][index].pop("current_budget_observation")
    actual = prior["cells"][7].pop("current_budget_observation")
    canonical = (json.dumps(prior, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    assert hashlib.sha256(canonical).hexdigest() == "aaea03354686ada4e716b4eb0eb24b9c1ab964d8e4e4e4210e5b960519dfdd89"
    assert (actual["mode"], actual["run_id"], actual["job_id"], actual["receipt_utc"]) == (
        "observe_budget", "37119043633", 111191419176, "2026-10-03T11:17:04.8848163Z")
    assert "2026-10-03 20:11 KST" in actual["source_addendum"]
    assert actual["marker_sha256"] == "02892ab81228f52767087c2196be84bbeb2f7c399fdd600f773b4f4b74fbce36"
    assert actual["budget_projector_sha256"] == reader.BUDGET_PROJECTOR_PIN[1]
    assert actual["result"] == {
        "sha256": "f68a695c50e26caa4f37984e190216c1bb5eb0553dd4c5c778edc3be521efdd1", "size": 6069,
        "result_fingerprint": "abbf03cb06df0c2b544992fdbfdb1c42346364d38e00d11ceedee00f37f59077",
        "recorded_prepared_fingerprint": "ec31c8bf37bda72326fce9b99df8c4751f9713ceb2885002b9f2dbc789cfe8ce",
        "registered_config_sha256": reader.TASK5_FRESH_R2_CONFIG_SHA256}
    assert actual["inference_budget_snapshot"] == {"total_seconds": 10800,
        "started_unix": 1791009579.9246106, "expires_unix": 1791020379.9246106,
        "remaining_seconds": 10724.012340545654, "wait_seconds": 0.0,
        "attempts_admitted": 1, "native_resumes": 0, "missing": {}}
    for key in ("terminal_commit", "output_commit", "retained_authority_sha256"):
        assert actual[key] == fresh_fixed[key]
    assert actual["result_body_verified"] and actual["approval_execution_skipped"]
    for key in ("payload_bodies_verified", "ledger_body_verified", "deliverable_bodies_verified",
                "grading_input_ready", "fresh_origin_authentication", "prepared_input_independently_verified",
                "git_parent_cas_independently_verified", "live_read_repeated_here", "replay_authorized"):
        assert actual[key] is False
    assert (actual["status"], actual["exit_code"], actual["cleanup_confirmed"], actual["grade"]) == ("failed", 1, True, None)
    assert actual["writer_acknowledgment"] == "not_established"
    assert fresh_row["terminal_details"]["budget"] is None and not fresh_row["read"]["payload_bodies_verified"]
    assert hashlib.sha256((ci.ROOT / "tasks/codex_budget_pilot/REPORT.md").read_bytes()).hexdigest() == (
        "88a37d8cfdae6c3c05a79db78827bfe2d59fdcd944067e4f6fcd7f387dddae0e")
    report = (ci.ROOT / "tasks/codex_budget_pilot/RETENTION_DIAGNOSTIC_REPORT.md").read_text()
    assert "Both r2 budget observations are consumed" in report
    assert "Both successful Task4 KEEP budgets remain unobserved" in " ".join(report.split())
    for value in actual["inference_budget_snapshot"].values():
        if type(value) in (int, float):
            assert str(value) in report

    source = reader.reader_identity(binding=binding)
    plan = intake.registration.compile_plan()
    cell = intake.controller._adapted_cell(plan["cells"][6])
    assert cell["config_sha256"] == intake.registration.seal(cell["config"]) == reader.TASK5_KEEP_R2_CONFIG_SHA256 == (
        "1bda6431161ff4d27e751b3475979f861eb875beb7d16a608c7649830f051286")
    assert plan["cells"][7]["config_sha256"] == reader.TASK5_FRESH_R2_CONFIG_SHA256 != cell["config_sha256"]
    monkeypatch.setattr(intake.registration, "compile_plan", lambda: deepcopy(plan))
    receipt = ci.project_cost_receipt(CostReceipt(status="partial", model_calls=1,
        known_cost_usd=Decimal("0.01"), model_cost_usd=Decimal("0.01"),
        usage={"input_tokens": 12, "cached_input_tokens": 8, "output_tokens": 3, "reasoning_tokens": 2},
        missing_reasons=("synthetic_missing_cost",)).as_dict())
    complete = {"run_id": cell["run_id"], "task_id": cell["task_id"], **cell["control"],
        "total_seconds": 10800, "attempt_seconds": 1800, "started_unix": 100.0, "expires_unix": 10900.0,
        "remaining_seconds": 100.0, "wait_seconds": 12.5, "attempts_admitted": 2, "native_resumes": 1}
    fields = ("total_seconds", "started_unix", "expires_unix", "remaining_seconds",
              "wait_seconds", "attempts_admitted", "native_resumes")
    download = fixtures.FreshResultHF.hf_hub_download

    def bounded_download(api, **kwargs):
        controls = [api.producer.TERMINAL, api.producer.CLAIM, api.producer.OUTPUT + "/" + output.MANIFEST]
        result_path = api.producer.OUTPUT + "/" + intake.RESULT
        assert kwargs["filename"] in {*controls, result_path}, "ledger/deliverable body forbidden"
        if kwargs["filename"] == result_path:
            assert kwargs["revision"] == api.fixed["output_commit"]
            assert [name for _, name in api.downloads] == controls
        return download(api, **kwargs)

    monkeypatch.setattr(fixtures.FreshResultHF, "hf_hub_download", bounded_download)

    def revisions(controls):
        monkeypatch.setattr(fixtures, "CLAIM_HEAD", controls["claim_commit"])
        monkeypatch.setattr(fixtures, "OUTPUT_HEAD", controls["output_commit"])

    def pin_controls(api):
        api.expected = {**api.fixed,
            "terminal_identity": owned._identity(retained._encoded(api.terminal)),
            "claim_identity": owned._identity(retained._encoded(api.claim)),
            "output_manifest_identity": owned._identity(retained._encoded(api.summary)),
            "output_objects_sha256": owned._digest(api.terminal["output_objects"]),
            "retained_authority_sha256": owned._digest(api.terminal["authority"])}

    def seal(api):
        revisions(api.fixed)
        api.bind_payload()
        api.seed()
        pin_controls(api)

    def make(snapshot=complete, *, profile=binding):
        controls = fixed if profile is binding else fresh_fixed
        revisions(controls)
        # The established fixture owns exclusive source/cache creation. No
        # additional source file is created or overwritten by this selector.
        api = _task5_fixture(plan, binding=profile, receipt=receipt, with_ledger=True,
                             terminal_head=controls["terminal_commit"])
        transports.append(api)
        api.fixed, api.profile = controls, profile
        api.files.pop(TASK5_FILE)
        api.payload["condition"] = plan["cells"][profile.ordinal]["config"]["condition_a"]["name"]
        api.payload["results"][0].update(status="error", deliverable_files=[], deliverable_file_records=[],
                                       observability={"task_deadline": deepcopy(snapshot)})
        api.summary.update(status="failed", exit_code=1)
        api.terminal.update(claim_commit=controls["claim_commit"], output_commit=controls["output_commit"])
        seal(api)
        return api

    def options(api, name, **changes):
        return {"expectation": api.profile.expectation, "binding": api.profile, "destination": tmp_path / name,
            "expected_reader_sha256": source["module_sha256"], "terminal_revision": api.fixed["terminal_commit"],
            "include_budget": True, "_test_api": api, **changes}

    def read(api, name, **changes):
        revisions(api.fixed)
        with monkeypatch.context() as synthetic:
            synthetic.setattr(reader, "TASK5_KEEP_R2_BUDGET_CONTROLS" if api.profile is binding
                              else "TASK5_FRESH_R2_BUDGET_CONTROLS", api.expected)
            return reader.observe_terminal(**options(api, name, **changes))

    def refuse(api, name, *, before_result=False, **changes):
        with pytest.raises((OSError, ValueError, TypeError, KeyError)):
            read(api, name, **changes)
        assert not (tmp_path / name / reader.TASK5_KEEP_R2_BUDGET_MARKER).exists()
        assert not (tmp_path / name / reader.BUDGET_MARKER).exists()
        if before_result:
            assert all(path != api.producer.OUTPUT + "/" + intake.RESULT for _, path in api.downloads)

    def captured(api):
        text = capsys.readouterr()
        assert not text.err
        assert all(secret not in text.out for secret in
            (str(tmp_path), api.repo, TOKEN, PRIVATE.decode().strip(), TASK5_FILE, "SECRET-LIKE-ERROR"))
        return json.loads(text.out)

    def cli(api, name):
        revisions(api.fixed)
        with monkeypatch.context() as synthetic:
            synthetic.setattr(reader, "TASK5_KEEP_R2_BUDGET_CONTROLS", api.expected)
            code = reader.main(["--observe-budget", "--terminal-revision", fixed["terminal_commit"],
                "--expected-producer-source", binding.expectation.source_sha,
                "--expected-request-sha256", binding.expectation.request_sha256,
                "--cell-id", binding.expectation.cell_id, "--expected-reader-sha256", source["module_sha256"],
                "--output", str(tmp_path / name)], _test_api=api)
        return code, captured(api)

    api = make()
    with monkeypatch.context() as early:
        early.setattr(retained, "_session", forbidden)
        early.setattr(reader, "_budget_projector", forbidden)
        assert reader.main([], _test_api=api) == 0 and captured(api)["cell_id"] == reader.FRESH_R1.expectation.cell_id
        for other_mode in ("--read", "--observe-terminal"):
            assert reader.main(["--observe-budget", other_mode], _test_api=api) == 2
            assert captured(api)["reason"] == "invalid_arguments"
        closed = (reader.FRESH_R1, reader.FRESH_R2, reader.KEEP_R2)
        for index, changes in enumerate((
            *({"binding": other} for other in (*closed, replace(binding), object(), reader.TASK5_FRESH_R2,
                                               reader.TASK5_FRESH_R1, reader.TASK5_KEEP_R1)),
            {"include_budget": 1}, {"expected_reader_sha256": "c" * 64},
            {"expectation": replace(binding.expectation, cell_id=reader.TASK5_FRESH_R2.expectation.cell_id)},
            {"expectation": replace(binding.expectation, source_sha="a" * 40)},
            {"expectation": replace(binding.expectation, request_sha256="b" * 64)},
            {"terminal_revision": producer.PREDECESSOR["terminal_commit"]},
            {"terminal_revision": None, "discover_terminal": True},
        )):
            name = "early-" + str(index)
            refuse(api, name, before_result=True, **changes)
            assert not (tmp_path / name).exists()
        for index, mutation in enumerate((
            lambda value: value["cells"][6].update(config_sha256=reader.TASK5_FRESH_R2_CONFIG_SHA256),
            lambda value: value["cells"][6]["config"]["execution"].update(timeout=1801),
        )):
            wrong = deepcopy(plan)
            mutation(wrong)
            early.setattr(intake.registration, "compile_plan", lambda: wrong)
            refuse(api, "config-" + str(index), before_result=True)
    real_bytes, real_import = output._bytes, builtins.__import__
    for bad_path in (Path(reader.__file__), *(Path(path) for path, _ in reader._frozen(binding).values()),
                     reader.BUDGET_PROJECTOR_PIN[0]):
        for missing in (False, True):
            def changed(path, **kwargs):
                if Path(path) == bad_path:
                    if missing:
                        raise FileNotFoundError("synthetic missing current source")
                    return real_bytes(path, **kwargs) + b"\n"
                return real_bytes(path, **kwargs)

            def no_import(name, *args, **kwargs):
                guarded = ("codex_budget_pilot_grade_readout" if bad_path == reader.BUDGET_PROJECTOR_PIN[0]
                           else "codex_retention_task5_keep_r2")
                if name == guarded:
                    return forbidden()
                return real_import(name, *args, **kwargs)

            with monkeypatch.context() as corrupt:
                corrupt.setattr(output, "_bytes", changed)
                corrupt.setattr(builtins, "__import__", no_import)
                corrupt.setattr(retained, "_session", forbidden)
                name = "pin-" + bad_path.stem + str(missing)
                refuse(api, name, before_result=True)
                assert not (tmp_path / name).exists()
    assert not api.calls and not effects
    with capsys.disabled():
        print("BOUNDARY exact KEEP binding/config/current pins; other profiles and tampered sources refused before imports/session")

    monkeypatch.setenv("HF_TOKEN", TOKEN)  # Authored synthetic token, never a credential.
    code, record = cli(api, "keep-budget")
    assert code == 0, {"boundary": "first_keep_result_budget_projection", "original_causes": failures[-1:]}
    assert record["format"] == reader.TASK5_KEEP_R2_BUDGET_FORMAT != reader.BUDGET_FORMAT
    assert record["mode"] == "observe_budget" and record["budget_observation_verified"] is True
    assert record["inference_budget_snapshot"] == {**{key: complete[key] for key in fields}, "missing": {}}
    assert record["inference_budget_snapshot"]["attempts_admitted"] != record["receipt"]["model_calls"]
    assert record["result"]["registered_config_sha256"] == reader.TASK5_KEEP_R2_CONFIG_SHA256
    assert record["result"]["sha256"] == owned._identity(api.files[intake.RESULT])["sha256"]
    assert (record["status"], record["exit_code"], record["cleanup_confirmed"], record["grade"]) == ("failed", 1, True, None)
    assert record["result_body_verified"] is True and record["payload_verification_scope"] == "inference_result_only"
    for key in ("payload_bodies_verified", "ledger_body_verified", "deliverable_bodies_verified", "grading_input_ready",
                "fresh_origin_authentication", "prepared_input_independently_verified", "git_parent_cas_independently_verified",
                "launch_authorized", "grading_launched", "admission_attempted", "replay_authorized", "invoice_complete"):
        assert record[key] is False
    assert record["writer_acknowledgment"] == "not_established" and record["recorded_publication_acknowledged"] is True
    assert record["receipt"] == receipt and record["commands"] == []
    assert set(record["unavailable"]) == {"detailed_failure", "recovery_exposure"}
    result_path = producer.OUTPUT + "/" + intake.RESULT
    assert api.downloads == [(fixed["terminal_commit"], producer.TERMINAL), (fixed["claim_commit"], producer.CLAIM),
        (fixed["output_commit"], producer.OUTPUT + "/" + output.MANIFEST), (fixed["output_commit"], result_path)]
    assert all(revision != retained.BRANCH for revision, _ in api.path_reads)
    marker = tmp_path / "keep-budget" / reader.TASK5_KEEP_R2_BUDGET_MARKER
    marker_bytes, calls = marker.read_bytes(), deepcopy(api.calls)
    assert marker.stat().st_mode & 0o777 == 0o600 and marker.parent.stat().st_mode & 0o777 == 0o700
    assert record["observation_sha256"] == owned._identity(marker_bytes)["sha256"]
    with pytest.raises(output.OutputPublicationRefused, match="^new_result_destination_required$"):
        read(api, "keep-budget")
    assert api.calls == calls and marker.read_bytes() == marker_bytes
    with capsys.disabled():
        print("BOUNDARY fixed controls/history then RESULT only; KEEP snapshot, private marker/readback and no-clobber verified")

    for index, mutation in enumerate((
        lambda api: api.terminal["authority"].update(provider_run_id=reader.TASK5_FRESH_R2.run_id),
        lambda api: api.terminal["authority"].update(provider_job_id=reader.TASK5_FRESH_R2.execution_job_id),
        lambda api: api.summary.update(source_sha=reader.TASK5_FRESH_R2.expectation.source_sha),
        lambda api: api.summary.update(cell_id=reader.TASK5_FRESH_R2.expectation.cell_id),
        lambda api: api.terminal.update(request_sha256=reader.TASK5_FRESH_R2.expectation.request_sha256),
        lambda api: api.claim.update(expected_parent=fixed["terminal_commit"]),
        lambda api: api.claim["predecessor"].update(exit_code=137),
        lambda api: api.summary.update(cleanup_confirmed=False),
        lambda api: api.terminal.update(publication_acknowledged=False),
    )):
        bad = make()
        mutation(bad)
        seal(bad)
        refuse(bad, "control-" + str(index), before_result=True)
    for key in ("terminal_identity", "claim_identity", "output_manifest_identity"):
        bad = make()
        bad.expected[key]["sha256"] = "0" * 64
        refuse(bad, "fixed-" + key, before_result=True)
    for key in ("output_objects_sha256", "retained_authority_sha256"):
        bad = make()
        bad.expected[key] = "0" * 64
        refuse(bad, key, before_result=True)
    bad = make()
    bad.expected["terminal_identity"]["size"] += 1
    refuse(bad, "fixed-size", before_result=True)
    for revision, path in ((fixed["claim_commit"], producer.CLAIM), (fixed["output_commit"], result_path),
                           (fixed["terminal_commit"], producer.OUTPUT + "/" + intake.LEDGER)):
        bad = make()
        bad.writers[revision][path] = "f" * 40
        refuse(bad, "history-" + str(len(transports)), before_result=True)
    bad = make()
    bad.corrupt = result_path
    refuse(bad, "result-hash-size")
    assert bad.downloads[-1] == (fixed["output_commit"], result_path)
    for index, mutation in enumerate((
        lambda value: value.update(source="synthetic-wrong/source"),
        lambda value: value.update(run_id="wrong-config-run"),
        lambda value: value.update(condition="wrong-condition"),
        lambda value: value.update(ordered_task_ids=[intake.registration.TASK4]),
        lambda value: value["results"][0].update(task_id=intake.registration.TASK4),
        lambda value: value["results"][0].update(observability=[]),
        lambda value: value["results"][0]["observability"].update(task_deadline=None),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(retention_bundle="fresh"),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(repetition=1),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(total_seconds=10801),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(attempt_seconds=1801),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(attempts_admitted=1.0),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(native_resumes=True),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(wait_seconds="12"),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(remaining_seconds=-1),
        lambda value: value["cost_ledger"].update(sha256="0" * 64),
    )):
        bad = make()
        mutation(bad.payload)
        seal(bad)
        refuse(bad, "payload-" + str(index))
        assert bad.downloads[-1] == (fixed["output_commit"], result_path)
    bad = make()
    bad.payload["result_fingerprint"] = "0" * 64
    bad.files[intake.RESULT] = (json.dumps(bad.payload, sort_keys=True) + "\n").encode()
    bad.seed()
    pin_controls(bad)
    refuse(bad, "fingerprint")
    absent = make({})
    del absent.payload["results"][0]["observability"]
    seal(absent)
    assert read(absent, "absent")["inference_budget_snapshot"] == {
        **dict.fromkeys(fields), "missing": dict.fromkeys(fields, "not_recorded")}
    nullable = make({"total_seconds": 10800, "remaining_seconds": None})
    assert read(nullable, "nullable")["inference_budget_snapshot"] == {
        "total_seconds": 10800, **dict.fromkeys(fields[1:]), "missing": {
            **dict.fromkeys(fields[1:], "not_recorded"), "remaining_seconds": "unavailable"}}
    zeros = make({"total_seconds": 10800, **dict.fromkeys(fields[1:], 0)})
    assert read(zeros, "zeros")["inference_budget_snapshot"] == {
        "total_seconds": 10800, **dict.fromkeys(fields[1:], 0), "missing": {}}
    with capsys.disabled():
        print("BOUNDARY mismatched control/source/task/config/fingerprint/history refused; missing/null/recorded-zero preserved")

    unresolved = make()
    writer = reader._write_no_clobber

    def lost_write(path, data, **kwargs):
        writer(path, data, **kwargs)
        if Path(path).name == reader.TASK5_KEEP_R2_BUDGET_MARKER:
            raise OSError("SECRET-LIKE-ERROR lost marker acknowledgment")

    with monkeypatch.context() as lost:
        lost.setattr(reader, "_write_no_clobber", lost_write)
        code, result = cli(unresolved, "unresolved")
        assert code == 2 and result["budget_observation_verified"] is False
        assert result["reason"] == "fresh_terminal_observation_unconfirmed"
    assert (tmp_path / "unresolved" / reader.TASK5_KEEP_R2_BUDGET_MARKER).is_file()
    calls = deepcopy(unresolved.calls)
    code, result = cli(unresolved, "unresolved")
    assert code == 2 and not result["budget_observation_verified"] and unresolved.calls == calls
    bad = make()
    bad.read_error = OSError("SECRET-LIKE-ERROR " + str(tmp_path))
    code, result = cli(bad, "private-error")
    assert code == 2 and result["reason"] == "fresh_budget_observation_refused"
    old, other = make(), make()
    with monkeypatch.context() as controls_only:
        controls_only.setattr(reader, "_budget_projector", forbidden)
        explicit = read(old, "controls-explicit", include_budget=False)
        arguments = options(other, "controls-default")
        del arguments["include_budget"]
        omitted = reader.observe_terminal(**arguments)
    assert explicit == omitted and explicit["outcome"] == "terminal_verified"
    assert "inference_budget_snapshot" not in explicit and explicit["unavailable"]["budget"]["reason"] == "not_recorded_in_terminal_controls"
    assert explicit["payload_bodies_verified"] is False and len(old.downloads) == len(other.downloads) == 3
    stopped = make()
    stopped.summary.update(status="stopped", exit_code=None)
    seal(stopped)
    record = read(stopped, "stopped-controls", include_budget=False)
    assert record["status"] == "stopped" and record["grade"] is None and len(stopped.downloads) == 3
    stopped.downloads.clear()
    refuse(stopped, "not-fixed-failed", before_result=True)
    failed_intake = make()
    with pytest.raises(output.OutputPublicationRefused, match="^fresh_result_success_required$"):
        reader.read_result(**{key: value for key, value in options(failed_intake, "not-success").items() if key != "include_budget"})
    assert all(path != result_path for _, path in failed_intake.downloads)

    # Only directly coupled fresh compatibility; never invoke its delivered test.
    fresh_cell = intake.controller._adapted_cell(plan["cells"][7])
    fresh_snapshot = {**complete, "run_id": fresh_cell["run_id"], **fresh_cell["control"]}
    fresh_api = make(fresh_snapshot, profile=reader.TASK5_FRESH_R2)
    record = read(fresh_api, "fresh-budget")
    assert record["format"] == reader.BUDGET_FORMAT and record["result"]["registered_config_sha256"] == reader.TASK5_FRESH_R2_CONFIG_SHA256
    assert record["inference_budget_snapshot"] == {**{key: fresh_snapshot[key] for key in fields}, "missing": {}}
    assert (tmp_path / "fresh-budget" / reader.BUDGET_MARKER).is_file()
    assert not (tmp_path / "fresh-budget" / reader.TASK5_KEEP_R2_BUDGET_MARKER).exists()
    fresh_control = make(fresh_snapshot, profile=reader.TASK5_FRESH_R2)
    with monkeypatch.context() as controls_only:
        controls_only.setattr(reader, "_budget_projector", forbidden)
        record = read(fresh_control, "fresh-controls", include_budget=False)
    assert len(fresh_control.downloads) == 3 and record["payload_bodies_verified"] is False
    assert reader.TASK5_KEEP_R2_BUDGET_CONTROLS == fixed and reader.TASK5_FRESH_R2_BUDGET_CONTROLS == fresh_fixed
    for name, digest in observer.CURRENT_DEPENDENCIES.items():
        assert hashlib.sha256((ci.ROOT / "batch-runner" / name).read_bytes()).hexdigest() == digest
    assert observer.bridge.fixed_evidence_sha256() == "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d"
    assert observer.bridge.fixed_evidence_sha256("retention/keep-r2") == "25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0"
    assert observer.bridge._fixed("retention/keep-r2").RESULT["intake_sha256"] == "4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4"
    with capsys.disabled():
        print("BOUNDARY private lost-ack/no-replay; unchanged fresh and controls-only behavior; current/historical evidence isolated")

    workflow_contract._assert_retention_execution_workflow_contract()
    workflow_contract._assert_retention_mode_routes()
    workflow = yaml.safe_load((ci.ROOT / ci.WORKFLOW).read_bytes())
    jobs, cells = workflow["jobs"], tuple(plan["order"])
    assert len(workflow_contract._BUDGET_CELLS) == 8 and set(workflow_contract._BUDGET_CELLS) == set(cells)
    steps = jobs[ci.PREPARE_JOB]["steps"]
    names = ("prepare", "execute", "observe_locator", "read_result", "observe_terminal", "observe_budget")
    for selected, flags in itertools.product((*cells, "unknown"), itertools.product((False, True), repeat=6)):
        modes = dict(zip(names, flags))
        values = {"inputs." + key: value for key, value in modes.items()}
        values.update({"inputs.cell_id == '" + cell_id + "'": selected == cell_id for cell_id in cells})
        reading, terminal, budget = (modes[name] and sum(flags) == 1 for name in ("read_result", "observe_terminal", "observe_budget"))
        for index in (9, 10, 11, 12, 13, 14):
            expected = ((reading and selected in cells[1:]) if index in (9, 10) else
                        ((reading or budget) and selected == cells[0]) if index in (11, 12) else
                        ((terminal or budget) and selected in cells[1:]))
            assert workflow_contract._boolean(steps[index]["if"], values) is expected
    preflight, step = steps[13:15]
    assert "secrets." not in preflight["run"]
    assert '"$(git rev-parse HEAD)" == "$REVIEWED_SOURCE_SHA"' in preflight["run"]
    assert "git status --porcelain=v1 --untracked-files=all" in preflight["run"]
    assert preflight["run"] == steps[9]["run"] + (
        'if [[ "$OBSERVE_BUDGET_ONLY" == true ]]; then\n'
        "  printf '%s\\n' '" + reader.BUDGET_PROJECTOR_PIN[1] + "  batch-runner/codex_budget_pilot_grade_readout.py' | sha256sum --check --status\nfi\n")
    pins = re.findall(r"'([0-9a-f]{64})  (batch-runner/[^']+)'", preflight["run"])
    expected = {"batch-runner/" + Path(path).name: digest for path, digest in reader._frozen(reader.TASK5_FRESH_R2).values()}
    expected.update({"batch-runner/" + Path(reader.__file__).name: source["module_sha256"],
                     "batch-runner/codex_budget_pilot_grade_readout.py": reader.BUDGET_PROJECTOR_PIN[1]})
    assert len(pins) == len(expected) and {path: digest for digest, path in pins} == expected
    assert all(hashlib.sha256((ci.ROOT / path).read_bytes()).hexdigest() == digest for digest, path in pins)
    assert step["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}", "OBSERVE_BUDGET_ONLY": "${{ inputs.observe_budget }}"}
    assert step["timeout-minutes"] == 4 and jobs[ci.PREPARE_JOB]["timeout-minutes"] == 20
    budget_case = workflow_contract._budget_terminal_selection()
    assert budget_case in step["run"] and "retention_terminal_args=(--observe-terminal --discover-terminal)" in step["run"]
    command = shlex.split(next(line for line in step["run"].replace("\\\n", "").splitlines() if line.startswith("env -u ")))
    assert command[:17] == ["env", "-u", "GITHUB_TOKEN", "-u", "GH_TOKEN", "-u", "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "-u", "ACTIONS_ID_TOKEN_REQUEST_URL", "-u", "ACTIONS_RUNTIME_TOKEN", "timeout", "--signal=KILL", "180s",
        "python3", "batch-runner/codex_retention_fresh_r1_result_intake.py", "${retention_terminal_args[@]}"]
    assert command[command.index("--expected-reader-sha256") + 1] == source["module_sha256"]
    assert "stderr.log" not in step["run"].split("# Only the reviewed reader")[1]
    assert 'tee -a "$GITHUB_STEP_SUMMARY" < "$retention_terminal_parent/receipt.json"' in step["run"]
    assert not effects and all(not api.commits for api in transports)
    assert subprocess.Popen is not REAL_POPEN and subprocess.Popen.__name__ == socket.create_connection.__name__ == "blocked"
    with capsys.disabled():
        print(json.dumps({"scope": "synthetic_paired_task5_keep_r2_result_only_budget_observation", "mode_cases": 576,
            "fixed_controls_before_result": True, "only_result_body_verified": True, "sealed_keep_config": True,
            "fresh_controls_only_paid_isolation": True, "current_historical_pins_separate": True,
            "later_actual_fresh_receipt_separate_from_synthetic_proof": True,
            "prior_json_fields_and_original_pilot_unchanged": True,
            "network_model_writer_child_paid_effects": len(effects)}, sort_keys=True))
