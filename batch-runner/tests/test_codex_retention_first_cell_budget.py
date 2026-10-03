"""One bounded offline proof for the legacy first-cell RESULT-only budget facade."""

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

import codex_retention_first_cell_budget as budget
import codex_retention_result_intake as intake
import codex_retention_fresh_r1_result_intake as reader
import codex_retention_grade_readout as observer
import codex_retention_task4_fresh_r1 as fresh_r1
import codex_retention_task4_fresh_r2 as fresh_r2
import codex_retention_task4_keep_r2 as keep_r2
import codex_retention_task5_fresh_r1 as task5_fresh_r1
import codex_retention_task5_keep_r1 as task5_keep_r1
import codex_retention_task5_keep_r2 as task5_keep_r2
import codex_retention_task5_fresh_r2 as task5_fresh_r2
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from core.cost_receipts import CostReceipt
from .test_codex_budget_pilot_retention import TOKEN, offline  # noqa: F401
# Resolve all established source/transport helper ownership at collection time.
from .test_codex_retention_ci import REAL_POPEN
from . import test_codex_retention_result_intake as first_fixtures
from . import test_codex_retention_fresh_r1_result_intake as fixtures
from . import test_codex_retention_ci_observation as workflow_contract
from .test_codex_retention_task5_fresh_r1_read import _task5_fixture, TASK5_FILE

ci, retained, output, owned = intake.ci, intake.retained, intake.output, intake.owned
FILE, PRIVATE = first_fixtures.FILE, first_fixtures.PRIVATE


def test_first_cell_budget_preserves_legacy_controls_and_result_only_boundary(tmp_path, monkeypatch, capsys):
    effects, transports, failures, verified = [], [], [], []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("first-cell budget crossed a live, paid, child, writer or full-payload boundary")

    producers = (fresh_r1, fresh_r2, keep_r2, task5_fresh_r1, task5_keep_r1, task5_keep_r2, task5_fresh_r2)
    ordinary_first_intake, ordinary_successor_intake = intake.read_result, reader.read_result
    for owner, names in (
        (ci, ("execute", "verify_approval", "verify_job_origin")),
        *((producer, ("execute", "_predecessor", "verify_terminal")) for producer in producers),
        *((admission, ("__init__",)) for admission in (
            ci._Admission, fresh_r1._FreshAdmission, fresh_r2._FreshR2Admission, keep_r2._KeepR2Admission,
            task5_fresh_r1._Task5FreshR1Admission, task5_keep_r1._Task5KeepR1Admission,
            task5_keep_r2._Task5KeepR2Admission, task5_fresh_r2._Task5FreshR2Admission)),
        (ci.LocalTransport, ("github_job_token", "authority_opener", "github", "azure")),
        (owned.LocalTransport, ("clock", "child", "process")),
        (ci.preparation, ("prepare_packet", "verify_packet")), (ci.historical, ("observe",)),
        (ci.controller, ("execute_first_cell", "stage_runtime", "_deadline")),
        (CodexTaskDeadlineStore, ("__init__",)), (CodexTaskDeadline, ("admit_attempt",)),
        (intake.retained_reader, ("prepare", "main")), (output, ("_hf_client", "publish", "_ledger")),
        (observer.bridge, ("prepare", "claim", "judge", "publish", "reconcile")), (observer.readout, ("main",)),
        (intake, ("read_result", "_payload", "bind_deliverable_file_records")),
        (reader, ("read_result", "bind_deliverable_file_records")),
        *((factory, ("create_commit", "list_repo_tree")) for factory in (first_fixtures.ResultHF, fixtures.FreshResultHF)),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    assert subprocess.Popen is not REAL_POPEN and subprocess.Popen.__name__ == "blocked"
    assert socket.create_connection.__name__ == socket.socket.connect.__name__ == "blocked"

    actual_verify = ci.verify_terminal

    def legacy_verify(*args, **kwargs):
        assert args[3] is None and kwargs == {"expectation": intake.EXPECTATION}
        verified.append(True)
        return actual_verify(*args, **kwargs)

    monkeypatch.setattr(ci, "verify_terminal", legacy_verify)
    actual_observe = budget.observe_budget

    def observed(**kwargs):
        try:
            return actual_observe(**kwargs)
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
            failures.append(chain)  # Never publish private exception strings.
            raise

    monkeypatch.setattr(budget, "observe_budget", observed)
    fixed = deepcopy(budget.CONTROLS)
    source = budget.reader_identity()
    artifact_hashes = {
        "tasks/codex_budget_pilot/retention_diagnostic_readout.json": "31f7d2b58d044a5548cb9998362b8b6ebaf2d428b4d679b4a42f4191d666814e",
        "tasks/codex_budget_pilot/RETENTION_DIAGNOSTIC_REPORT.md": "12ad05a9483461161e431a8fef834c90cf62832a0177e8a514cb32b3ce32b699",
        "tasks/codex_budget_pilot/REPORT.md": "88a37d8cfdae6c3c05a79db78827bfe2d59fdcd944067e4f6fcd7f387dddae0e",
    }
    for path, digest in artifact_hashes.items():
        assert hashlib.sha256((ci.ROOT / path).read_bytes()).hexdigest() == digest
    readout = json.loads((ci.ROOT / "tasks/codex_budget_pilot/retention_diagnostic_readout.json").read_bytes())
    first = readout["cells"][0]
    assert fixed == {
        "terminal_commit": first["terminal"]["revision"],
        "terminal_identity": {"sha256": first["terminal"]["sha256"], "size": first["terminal"]["bytes"]},
        "claim_commit": first["claim"]["revision"], "output_commit": first["output_manifest"]["revision"],
        "output_manifest_identity": {"sha256": first["output_manifest"]["sha256"], "size": first["output_manifest"]["bytes"]}}
    assert (budget.CELL_ID, budget.PRODUCER_SOURCE, budget.RUN_ID, budget.JOB_ID, budget.REQUEST_SHA256) == (
        first["cell_id"], first["producer"]["source_sha"], first["producer"]["run_id"],
        first["producer"]["execution_job_id"], first["producer"]["request_sha256"])
    assert first["producer"]["workflow_id"] == 370228282 and first["producer"]["attempt"] == 1
    assert first["claim"]["sha256"] is first["claim"]["bytes"] is first["output_objects_sha256"] is first.get("exit_code") is None
    assert "claim_identity" not in fixed and "output_objects_sha256" not in fixed and "exit_code" not in fixed
    assert first["read"]["successful_intake_established"] is True
    assert (first["grade"]["score"], first["grade"]["included_max"], first["grade"]["included_percent"], first["grade"]["full_percent"]) == (
        "30.6", "45", "68.0", "54.64")
    assert all("current_budget_observation" not in readout["cells"][index] for index in (0, 3))
    assert all("current_budget_observation" in readout["cells"][index] for index in (1, 2, 4, 5, 6, 7))
    assert reader.TASK5_KEEP_R1.materialized_grader_source_sha256 is None
    plan = intake.registration.compile_plan()
    cell = intake.controller._adapted_cell(plan["cells"][0])
    assert cell["config_sha256"] == intake.registration.seal(cell["config"]) == budget.CONFIG_SHA256 == (
        "08b29f44cb57312fd5757a3192c1a64855922bcd3d48d8e02fed96c4160683cb")
    assert cell["control"] == {"condition": "retention_bundle_v1", "retention_bundle": "keep", "repetition": 1}
    # One real inert compilation, then reuse that same exclusively owned fixture.
    monkeypatch.setattr(intake.registration, "compile_plan", lambda: deepcopy(plan))
    receipt = ci.project_cost_receipt(CostReceipt(status="partial", model_calls=1,
        known_cost_usd=Decimal("0.01"), model_cost_usd=Decimal("0.01"),
        usage={"input_tokens": 12, "cached_input_tokens": 8, "output_tokens": 3, "reasoning_tokens": 2},
        missing_reasons=("synthetic_missing_cost",)).as_dict())
    fields = ("total_seconds", "started_unix", "expires_unix", "remaining_seconds", "wait_seconds", "attempts_admitted", "native_resumes")
    full_snapshot = {"run_id": cell["run_id"], "task_id": cell["task_id"], **cell["control"],
        "total_seconds": 10800, "attempt_seconds": 1800, "started_unix": 100.0, "expires_unix": 10900.0,
        "remaining_seconds": 100.0, "wait_seconds": 12.5, "attempts_admitted": 2, "native_resumes": 1}
    second_file = FILE.rsplit("/", 1)[0] + "/second.txt"

    def first_revisions():
        for name, key in (("CLAIM_HEAD", "claim_commit"), ("OUTPUT_HEAD", "output_commit"), ("TERMINAL_HEAD", "terminal_commit")):
            monkeypatch.setattr(first_fixtures, name, fixed[key])

    def pin(api):
        api.expected = {**fixed, "terminal_identity": owned._identity(retained._encoded(api.terminal)),
                        "output_manifest_identity": owned._identity(retained._encoded(api.summary))}

    def seal(api):
        first_revisions()
        api.bind_payload()
        api.seed()
        pin(api)

    unset = object()

    def make(snapshot=unset, *, with_ledger=True):
        first_revisions()
        api = first_fixtures.ResultHF(plan, receipt=receipt, with_ledger=with_ledger)
        transports.append(api)
        api.payload.pop("source")
        assert "condition" not in api.payload
        api.payload["publication_generation"] = "legacy-first-cell:36696961231:1"
        api.summary["exit_code"] = None
        api.files[second_file] = b"x"
        row = api.payload["results"][0]
        row.update(deliverable_files=[FILE, second_file], deliverable_file_records=[
            {"path": name, **owned._identity(api.files[name])} for name in (FILE, second_file)])
        row["observability"] = {"task_deadline": deepcopy(full_snapshot if snapshot is unset else snapshot)}
        api.fixed = fixed
        seal(api)
        return api

    first_download = first_fixtures.ResultHF.hf_hub_download
    controls = (ci.TERMINAL, ci.CLAIM, ci.OUTPUT + "/" + output.MANIFEST)
    result_path = ci.OUTPUT + "/" + intake.RESULT

    def bounded_first_download(api, **kwargs):
        assert kwargs["filename"] in {*controls, result_path}, "ledger/deliverable body forbidden"
        if kwargs["filename"] == result_path:
            assert kwargs["revision"] == fixed["output_commit"]
            assert [path for _, path in api.downloads] == [controls[0], *controls, *controls[1:]]
        return first_download(api, **kwargs)

    monkeypatch.setattr(first_fixtures.ResultHF, "hf_hub_download", bounded_first_download)

    def options(api, name, **changes):
        return {"expectation": intake.EXPECTATION, "destination": tmp_path / name,
            "expected_reader_sha256": source["module_sha256"], "terminal_revision": fixed["terminal_commit"],
            "_test_api": api, **changes}

    def read(api, name, **changes):
        first_revisions()
        with monkeypatch.context() as synthetic:
            synthetic.setattr(budget, "CONTROLS", api.expected)
            return budget.observe_budget(**options(api, name, **changes))

    def refuse(api, name, *, before_result=False, **changes):
        with pytest.raises((OSError, ValueError, TypeError, KeyError)):
            read(api, name, **changes)
        assert not (tmp_path / name / budget.MARKER).exists()
        if before_result:
            assert all(path != result_path for _, path in api.downloads)

    def captured(api):
        text = capsys.readouterr()
        assert text.err == ""
        assert all(secret not in text.out for secret in (str(tmp_path), api.repo, TOKEN, PRIVATE.decode().strip(),
            FILE, second_file, TASK5_FILE, "SECRET-LIKE-ERROR", "legacy-first-cell:36696961231:1"))
        return json.loads(text.out)

    def cli(api, name):
        first_revisions()
        with monkeypatch.context() as synthetic:
            synthetic.setattr(budget, "CONTROLS", api.expected)
            code = budget.main(["--observe-budget", "--terminal-revision", fixed["terminal_commit"],
                "--expected-producer-source", budget.PRODUCER_SOURCE, "--expected-request-sha256", budget.REQUEST_SHA256,
                "--cell-id", budget.CELL_ID, "--expected-reader-sha256", source["module_sha256"],
                "--output", str(tmp_path / name)], _test_api=api)
        return code, captured(api)

    api = make()
    with monkeypatch.context() as early:
        early.setattr(retained, "_session", forbidden)
        assert budget.main([]) == 0 and captured(api)["read_attempted"] is False
        for args in (["--read"], ["--observe-terminal"], ["--observe-budget", "--discover-terminal"], ["--output", str(tmp_path)]):
            assert budget.main(args) == 2 and captured(api)["budget_observation_verified"] is False
        for index, changes in enumerate((
            {"expectation": object()}, {"expected_reader_sha256": "0" * 64},
            {"expectation": replace(intake.EXPECTATION, source_sha="a" * 40)},
            {"expectation": replace(intake.EXPECTATION, request_sha256="b" * 64)},
            {"expectation": replace(intake.EXPECTATION, cell_id="unknown")},
            *({"expectation": profile.expectation} for profile in (
                reader.FRESH_R1, reader.FRESH_R2, reader.KEEP_R2, reader.TASK5_FRESH_R1,
                reader.TASK5_KEEP_R1, reader.TASK5_KEEP_R2, reader.TASK5_FRESH_R2)),
            {"terminal_revision": None}, {"terminal_revision": "c" * 40}, {"destination": Path("relative")},
        )):
            refuse(api, "early-" + str(index), before_result=True, **changes)
            assert not (tmp_path / ("early-" + str(index))).exists()
        for index, mutation in enumerate((
            lambda value: value["cells"][0].update(config_sha256=reader.KEEP_R2_CONFIG_SHA256),
            lambda value: value["cells"][0]["config"]["execution"].update(timeout=1801),
            lambda value: value["cells"][0]["control"].update(repetition=2),
        )):
            wrong = deepcopy(plan)
            mutation(wrong)
            early.setattr(intake.registration, "compile_plan", lambda: wrong)
            refuse(api, "sealed-config-" + str(index), before_result=True)
    real_bytes, real_import = output._bytes, builtins.__import__
    for bad_path in (Path(budget.__file__), *(Path(budget.__file__).with_name(name) for name, _ in budget.FROZEN.values())):
        for missing in (False, True):
            def changed(path, **kwargs):
                if Path(path) == bad_path:
                    if missing:
                        raise FileNotFoundError("synthetic missing current dependency")
                    return real_bytes(path, **kwargs) + b"\n"
                return real_bytes(path, **kwargs)

            def no_import(name, *args, **kwargs):
                if name in {"codex_retention_result_intake", "codex_budget_pilot_grade_readout"}:
                    return forbidden()
                return real_import(name, *args, **kwargs)

            with monkeypatch.context() as corrupt:
                corrupt.setattr(output, "_bytes", changed)
                corrupt.setattr(builtins, "__import__", no_import)
                corrupt.setattr(retained, "_session", forbidden)
                name = "pin-" + bad_path.stem + str(missing)
                refuse(api, name, before_result=True)
                assert not (tmp_path / name).exists()
    assert not api.calls and not effects and not verified
    with capsys.disabled():
        print("BOUNDARY exact legacy identity/config; changed/missing current pins before imports/credentials; historical missing fields remain absent")

    monkeypatch.setenv("HF_TOKEN", TOKEN)  # Authored synthetic token, never a credential.
    api = make()
    code, record = cli(api, "legacy-budget")
    assert code == 0, {"boundary": "first_legacy_result_only_budget", "original_causes": failures[-1:]}
    assert record["format"] == budget.FORMAT and record["mode"] == "observe_budget"
    assert record["inference_budget_snapshot"] == {**{key: full_snapshot[key] for key in fields}, "missing": {}}
    assert record["result"] == {**owned._identity(api.files[intake.RESULT]),
        "result_fingerprint": api.payload["result_fingerprint"],
        "recorded_prepared_fingerprint": api.payload["prepared_fingerprint"], "registered_config_sha256": budget.CONFIG_SHA256}
    assert (record["status"], record["exit_code"], record["cleanup_confirmed"], record["grade"]) == ("succeeded", None, True, None)
    assert record["exit_code_missing_reason"] == "not_recorded_in_terminal_controls"
    assert record["expected_execution_job_id"] == record["recorded_provider_job_id"] == budget.JOB_ID
    assert record["expected_provider"] == {"workflow_id": 370228282, "workflow": ci.WORKFLOW, "run_id": budget.RUN_ID, "attempt": 1}
    assert record["claim_identity"] == api.terminal["claim_identity"]
    assert record["output_objects_sha256"] == owned._digest(api.terminal["output_objects"])
    assert record["retained_authority_sha256"] == owned._digest(api.terminal["authority"])
    assert record["result_body_verified"] is True and record["payload_verification_scope"] == "inference_result_only"
    for key in ("payload_bodies_verified", "ledger_body_verified", "deliverable_bodies_verified", "grading_input_ready",
        "fresh_origin_authentication", "prepared_input_independently_verified", "git_parent_cas_independently_verified",
        "launch_authorized", "grading_launched", "admission_attempted", "replay_authorized", "invoice_complete",
        "full_intake_established_by_this_observation", "delivery_established_by_this_observation", "grade_established_by_this_observation"):
        assert record[key] is False
    assert record["writer_acknowledgment"] == "not_established" and record["recorded_publication_acknowledged"] is True
    assert record["receipt"] == receipt and record["commands"] == []
    assert record["declared_payload_roles"] == {"inference_result": 1, "ledger": 1, "deliverables": 2}
    assert not {"intake_verified", "results", "raw_payload", "stderr", "error", "deliverable_files"} & record.keys()
    assert set(record["unavailable"]) == {"detailed_failure", "recovery_exposure"}
    marker = tmp_path / "legacy-budget" / budget.MARKER
    marker_bytes, calls = marker.read_bytes(), deepcopy(api.calls)
    assert owned._identity(marker_bytes)["sha256"] == record["observation_sha256"]
    assert marker.stat().st_mode & 0o777 == 0o600 and marker.parent.stat().st_mode & 0o777 == 0o700
    assert not (marker.parent / intake.MARKER).exists() and verified
    with pytest.raises(output.OutputPublicationRefused, match="^new_result_destination_required$"):
        read(api, "legacy-budget")
    assert api.calls == calls and marker.read_bytes() == marker_bytes

    # The primary terminal is pinned before any dependent read or metadata call.
    for key, value in (("sha256", "0" * 64), ("size", api.expected["terminal_identity"]["size"] + 1)):
        bad = make()
        bad.expected["terminal_identity"][key] = value
        count = len(verified)
        refuse(bad, "primary-" + key, before_result=True)
        assert len(verified) == count and bad.downloads == [(fixed["terminal_commit"], ci.TERMINAL)]
        assert all(paths == (ci.TERMINAL,) for _, paths in bad.path_reads)
    for index, mutation in enumerate((
        lambda item: item.terminal.update(claim_commit="0" * 40),
        lambda item: item.terminal.update(output_commit="1" * 40),
        lambda item: item.terminal["claim_identity"].update(sha256="0" * 64),
        lambda item: item.terminal["claim_identity"].update(size=True),
        lambda item: item.terminal["output_objects"][0].update(sha256="0" * 64),
        lambda item: item.terminal["authority"].update(provider_run_id=reader.KEEP_R2.run_id),
        lambda item: item.terminal["authority"].update(provider_job_id=reader.KEEP_R2.execution_job_id),
        lambda item: item.terminal.update(request_sha256="0" * 64),
        lambda item: item.terminal.update(publication_acknowledged=False),
    )):
        bad = make()
        mutation(bad)
        bad.trees[fixed["terminal_commit"]][ci.TERMINAL] = retained._encoded(bad.terminal)
        pin(bad)
        refuse(bad, "nested-" + str(index), before_result=True)
    for key, value in (("sha256", "0" * 64), ("size", api.expected["output_manifest_identity"]["size"] + 1)):
        bad = make()
        bad.expected["output_manifest_identity"][key] = value
        refuse(bad, "manifest-pin-" + key, before_result=True)
    for index, mutation in enumerate((
        lambda item: item.summary.update(source_sha=reader.KEEP_R2.expectation.source_sha),
        lambda item: item.summary.update(cell_id=reader.KEEP_R2.expectation.cell_id),
        lambda item: item.summary.update(status="failed", exit_code=1),
        lambda item: item.summary.update(exit_code=True),
        lambda item: item.summary.update(cleanup_confirmed=False),
        lambda item: item.claim.update(expected_parent=fixed["terminal_commit"]),
        lambda item: item.claim["predecessor"].update(cell_id="wrong-predecessor"),
    )):
        bad = make()
        mutation(bad)
        seal(bad)
        refuse(bad, "control-" + str(index), before_result=True)
    for index, (revision, name) in enumerate((
        (fixed["claim_commit"], ci.CLAIM), (fixed["output_commit"], result_path),
        (fixed["terminal_commit"], ci.OUTPUT + "/" + intake.LEDGER), (fixed["output_commit"], ci.OUTPUT + "/" + FILE),
    )):
        bad = make()
        bad.writers[revision][name] = "e" * 40
        refuse(bad, "history-" + str(index), before_result=True)
    for index, name in enumerate((TASK5_FILE, FILE.replace("report.txt", "../report.txt"), FILE.replace("report.txt", "state.sqlite"))):
        bad = make()
        bad.files[name] = bad.files.pop(FILE)
        seal(bad)
        refuse(bad, "manifest-path-" + str(index), before_result=True)
    for index, mutation in enumerate((
        lambda item: item.update(size=True), lambda item: item.update(size=-1),
        lambda item: item.update(sha256="not-a-hash"), lambda item: item.update(extra="unknown-field"),
    )):
        bad = make()
        mutation(next(item for item in bad.summary["files"] if item["path"] == second_file))
        manifest = retained._encoded(bad.summary)
        name = ci.OUTPUT + "/" + output.MANIFEST
        bad.terminal["output_objects"] = [retained._object(name, manifest) if item["path"] == name else item
                                          for item in bad.terminal["output_objects"]]
        bad.trees[fixed["output_commit"]][name] = bad.trees[fixed["terminal_commit"]][name] = manifest
        bad.trees[fixed["terminal_commit"]][ci.TERMINAL] = retained._encoded(bad.terminal)
        pin(bad)
        refuse(bad, "manifest-metadata-" + str(index), before_result=True)
    with capsys.disabled():
        print("BOUNDARY pinned primary before dependencies; real legacy verifier; nested controls/immutable history and metadata-only nonempty deliverables")

    bad = make()
    bad.corrupt = result_path
    refuse(bad, "result-size-hash")
    for index, mutation in enumerate((
        lambda value: value.update(source="synthetic-wrong/source"),
        lambda value: value.update(run_id="wrong-config-run"),
        lambda value: value.update(condition="wrong-condition"),
        lambda value: value.update(publication_generation="../not-legal"),
        lambda value: value.update(ordered_task_ids=[intake.registration.TASK5]),
        lambda value: value["results"][0].update(task_id=intake.registration.TASK5),
        lambda value: value["results"][0].update(status="error"),
        lambda value: value["results"][0].update(problem_solving_cost=None),
        lambda value: value["results"][0].update(deliverable_files=[]),
        lambda value: value["results"][0].update(deliverable_files=[FILE, FILE]),
        lambda value: value["results"][0].update(deliverable_file_records=[]),
        lambda value: value["results"][0]["deliverable_file_records"].reverse(),
        lambda value: value["results"][0]["deliverable_file_records"][1].update(size=True),
        lambda value: value["results"][0]["deliverable_file_records"][0].update(sha256="0" * 64),
        lambda value: value["results"][0]["deliverable_file_records"][0].update(extra=1),
        lambda value: value["cost_ledger"].update(sha256="0" * 64),
        lambda value: value["cost_ledger"].update(path="another-ledger.jsonl"),
        lambda value: value["results"][0].update(observability=None),
        lambda value: value["results"][0].update(observability=[]),
        lambda value: value["results"][0]["observability"].update(task_deadline=None),
        lambda value: value["results"][0]["observability"].update(task_deadline=[]),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(retention_bundle="fresh"),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(repetition=2),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(total_seconds=10801),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(attempt_seconds=1801),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(attempts_admitted=1.0),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(attempts_admitted=None),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(native_resumes=True),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(wait_seconds=None),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(total_seconds=0),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(wait_seconds="12"),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(remaining_seconds=-1),
    )):
        bad = make()
        mutation(bad.payload)
        seal(bad)
        refuse(bad, "payload-" + str(index))
    bad = make()
    bad.payload["result_fingerprint"] = "0" * 64
    bad.files[intake.RESULT] = retained._encoded(bad.payload)
    bad.seed()
    pin(bad)
    refuse(bad, "fingerprint")
    for name, snapshot, missing in (
        ("not-recorded", {}, {key: "not_recorded" for key in fields}),
        ("null", {**full_snapshot, "started_unix": None, "expires_unix": None, "remaining_seconds": None},
         {key: "unavailable" for key in ("started_unix", "expires_unix", "remaining_seconds")}),
        ("zero", {**full_snapshot, "remaining_seconds": 0.0, "wait_seconds": 0.0, "attempts_admitted": 0, "native_resumes": 0}, {}),
    ):
        point = make(snapshot)
        record = read(point, name)
        assert record["inference_budget_snapshot"] == {**{key: snapshot.get(key) for key in fields}, "missing": missing}
    absent = make(with_ledger=False)
    absent.payload["results"][0].pop("observability")
    seal(absent)
    record = read(absent, "absent-observability-and-ledger")
    assert record["inference_budget_snapshot"] == {**dict.fromkeys(fields), "missing": {key: "not_recorded" for key in fields}}
    assert record["declared_payload_roles"]["ledger"] == 0 and "bound_ledger_export" in record["missing"]
    explicit = make()
    explicit.payload.update(source=plan["inputs"]["repo_id"], condition=cell["config"]["condition_a"]["name"])
    explicit.summary["exit_code"] = 0
    seal(explicit)
    record = read(explicit, "optional-legacy-metadata")
    assert record["exit_code"] == 0 and "exit_code_missing_reason" not in record

    writer = budget._write_no_clobber
    for failure in ("write", "readback"):
        unresolved, name = make(), "lost-" + failure

        def lost_write(path, data, **kwargs):
            writer(path, data, **kwargs)
            if Path(path).name == budget.MARKER:
                raise OSError("SECRET-LIKE-ERROR lost marker acknowledgment")

        def lost_readback(path, **kwargs):
            if Path(path).name == budget.MARKER:
                raise OSError("SECRET-LIKE-ERROR lost marker readback")
            return real_bytes(path, **kwargs)

        with monkeypatch.context() as lost:
            if failure == "write":
                lost.setattr(budget, "_write_no_clobber", lost_write)
            else:
                lost.setattr(output, "_bytes", lost_readback)
            code, record = cli(unresolved, name)
            assert code == 2 and record["reason"] == "first_cell_budget_observation_unconfirmed"
        assert (tmp_path / name / budget.MARKER).is_file()
        calls = deepcopy(unresolved.calls)
        code, record = cli(unresolved, name)
        assert code == 2 and not record["budget_observation_verified"] and unresolved.calls == calls
    bad = make()
    with monkeypatch.context() as private_error:
        private_error.setattr(bad, "get_paths_info", lambda **kwargs: (_ for _ in ()).throw(OSError("SECRET-LIKE-ERROR " + str(tmp_path))))
        code, record = cli(bad, "private-error")
        assert code == 2 and record["reason"] == "first_cell_budget_observation_refused"
    with capsys.disabled():
        print("BOUNDARY legacy generation/optional metadata; exact RESULT fingerprint/receipt; missing/null/zero; private lost-ack/readback/no-replay")

    # Seven new synthetic compatibility observations, not old selectors or live reads.
    profiles = (reader.FRESH_R1, reader.FRESH_R2, reader.KEEP_R2, reader.TASK5_FRESH_R1,
                reader.TASK5_KEEP_R1, reader.TASK5_KEEP_R2, reader.TASK5_FRESH_R2)
    names = ("FRESH_R1", "FRESH_R2", "KEEP_R2", "TASK5_FRESH_R1", "TASK5_KEEP_R1", "TASK5_KEEP_R2", "TASK5_FRESH_R2")
    successor_download = fixtures.FreshResultHF.hf_hub_download

    def bounded_successor_download(api, **kwargs):
        allowed = (api.producer.TERMINAL, api.producer.CLAIM, api.producer.OUTPUT + "/" + output.MANIFEST)
        path = api.producer.OUTPUT + "/" + intake.RESULT
        assert kwargs["filename"] in {*allowed, path}
        if kwargs["filename"] == path:
            assert kwargs["revision"] == api.fixed["output_commit"] and [name for _, name in api.downloads] == list(allowed)
        return successor_download(api, **kwargs)

    monkeypatch.setattr(fixtures.FreshResultHF, "hf_hub_download", bounded_successor_download)
    historical_controls = {name: deepcopy(getattr(reader, name + "_BUDGET_CONTROLS")) for name in names}
    for profile, label in zip(profiles, names):
        controls = historical_controls[label]
        monkeypatch.setattr(fixtures, "CLAIM_HEAD", controls["claim_commit"])
        monkeypatch.setattr(fixtures, "OUTPUT_HEAD", controls["output_commit"])
        task4 = profile.ordinal < 4
        factory = fixtures.FreshResultHF if task4 else _task5_fixture
        api = factory(plan, binding=profile, receipt=receipt, with_ledger=True, terminal_head=controls["terminal_commit"])
        transports.append(api)
        api.fixed = controls
        api.claim["authority"]["provider_job_id"] = profile.execution_job_id
        api.terminal["authority"] = deepcopy(api.claim["authority"])
        api.terminal.update(claim_commit=controls["claim_commit"], output_commit=controls["output_commit"])
        selected_cell = intake.controller._adapted_cell(plan["cells"][profile.ordinal])
        api.payload["condition"] = selected_cell["config"]["condition_a"]["name"]
        row = api.payload["results"][0]
        successor_snapshot = {**full_snapshot, "run_id": selected_cell["run_id"],
            "task_id": selected_cell["task_id"], **selected_cell["control"],
            "native_resumes": 1 if profile.retention_bundle == "keep" else 0}
        row["observability"] = {"task_deadline": successor_snapshot}
        if profile is not reader.KEEP_R2:
            api.files.pop(FILE if task4 else TASK5_FILE)
            row.update(status="error", deliverable_files=[], deliverable_file_records=[])
            api.summary.update(status="failed", exit_code=1)
        api.bind_payload()
        api.seed()
        expected = {**controls, "terminal_identity": owned._identity(retained._encoded(api.terminal)),
            "claim_identity": owned._identity(retained._encoded(api.claim)),
            "output_manifest_identity": owned._identity(retained._encoded(api.summary)),
            "output_objects_sha256": owned._digest(api.terminal["output_objects"])}
        if "retained_authority_sha256" in controls:
            expected["retained_authority_sha256"] = owned._digest(api.terminal["authority"])
        args = {"expectation": profile.expectation, "binding": profile,
            "expected_reader_sha256": reader.reader_identity(binding=profile)["module_sha256"],
            "terminal_revision": controls["terminal_commit"], "_test_api": api}
        with monkeypatch.context() as compatibility:
            compatibility.setattr(reader, label + "_BUDGET_CONTROLS", expected)
            record = reader.observe_terminal(**args, destination=tmp_path / (label + "-budget"), include_budget=True)
        assert record["result_body_verified"] is True and record["payload_bodies_verified"] is False
        assert record["grading_input_ready"] is False and record["grade"] is None
        assert record["status"] == ("succeeded" if profile is reader.KEEP_R2 else "failed")
        assert record["inference_budget_snapshot"] == {**{key: successor_snapshot[key] for key in fields}, "missing": {}}
        assert record["supplied_request_binding"] == reader._request_context(profile)
        api.downloads.clear()
        with monkeypatch.context() as controls_only:
            controls_only.setattr(reader, "_budget_projector", forbidden)
            if profile is reader.KEEP_R2:
                with pytest.raises(output.OutputPublicationRefused, match="^fresh_terminal_unsuccessful_required$"):
                    reader.observe_terminal(**args, destination=tmp_path / (label + "-terminal"))
                assert len(api.downloads) == 1
            else:
                record = reader.observe_terminal(**args, destination=tmp_path / (label + "-terminal"))
                assert record["payload_bodies_verified"] is False and len(api.downloads) == 3
                assert "inference_budget_snapshot" not in record and record["unavailable"]["budget"]["reason"] == "not_recorded_in_terminal_controls"
        assert all(path != api.producer.OUTPUT + "/" + intake.RESULT for _, path in api.downloads)
    assert all(getattr(reader, name + "_BUDGET_CONTROLS") == saved for name, saved in historical_controls.items())
    assert budget.CONTROLS == fixed and budget.reader_identity() == source
    assert ordinary_first_intake.__name__ == ordinary_successor_intake.__name__ == "read_result"
    for name, digest in observer.CURRENT_DEPENDENCIES.items():
        assert hashlib.sha256((ci.ROOT / "batch-runner" / name).read_bytes()).hexdigest() == digest
    assert observer.bridge.fixed_evidence_sha256() == "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d"
    assert observer.bridge.fixed_evidence_sha256("retention/keep-r2") == "25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0"
    for path, digest in artifact_hashes.items():
        assert hashlib.sha256((ci.ROOT / path).read_bytes()).hexdigest() == digest
    with capsys.disabled():
        print("BOUNDARY seven existing budget profiles/ordinary controls unchanged; historical intake/grading/data bytes and six observations retained")

    workflow_contract._assert_retention_execution_workflow_contract()
    workflow_contract._assert_retention_mode_routes()
    workflow = yaml.safe_load((ci.ROOT / ci.WORKFLOW).read_bytes())
    jobs, cells = workflow["jobs"], tuple(plan["order"])
    steps = jobs[ci.PREPARE_JOB]["steps"]
    assert len(workflow_contract._BUDGET_CELLS) == 8 and set(workflow_contract._BUDGET_CELLS) == set(cells)
    assert len(workflow_contract._BUDGET_CASES) == 7 and {cell for cell, _, _ in workflow_contract._BUDGET_CASES} == set(cells[1:])
    mode_names = ("prepare", "execute", "observe_locator", "read_result", "observe_terminal", "observe_budget")
    mode_cases = 0
    for selected, flags in itertools.product((*cells, "unknown"), itertools.product((False, True), repeat=6)):
        modes = dict(zip(mode_names, flags))
        values = {"inputs." + key: value for key, value in modes.items()}
        values.update({"inputs.cell_id == '" + cell_id + "'": selected == cell_id for cell_id in cells})
        reading, terminal, budgeting = (modes[name] and sum(flags) == 1 for name in ("read_result", "observe_terminal", "observe_budget"))
        for index in (9, 10, 11, 12, 13, 14):
            expected = ((reading and selected in cells[1:]) if index in (9, 10) else
                        ((reading or budgeting) and selected == cells[0]) if index in (11, 12) else
                        ((terminal or budgeting) and selected in cells[1:]))
            assert workflow_contract._boolean(steps[index]["if"], values) is expected
        mode_cases += 1
    assert mode_cases == 576
    preflight, step = steps[11:13]
    assert preflight["if"] == step["if"] == workflow_contract._first_intake_condition()
    assert preflight["run"].endswith(workflow_contract._first_budget_preflight())
    assert workflow_contract._first_budget_selection() in step["run"]
    pins = re.findall(r"'([0-9a-f]{64})  (batch-runner/[^']+)'", preflight["run"])
    expected_pins = {"batch-runner/" + name: digest for name, digest in budget.FROZEN.values()}
    expected_pins["batch-runner/codex_retention_first_cell_budget.py"] = source["module_sha256"]
    assert len(pins) == len(expected_pins) and {path: digest for digest, path in pins} == expected_pins
    assert all(hashlib.sha256((ci.ROOT / path).read_bytes()).hexdigest() == digest for digest, path in pins)
    assert preflight["env"] == {"OBSERVE_BUDGET_ONLY": "${{ inputs.observe_budget }}"} and "secrets." not in preflight["run"]
    assert '"$(git rev-parse HEAD)" == "$REVIEWED_SOURCE_SHA"' in preflight["run"]
    assert "git status --porcelain=v1 --untracked-files=all" in preflight["run"]
    assert step["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}", **preflight["env"]}
    assert step["timeout-minutes"] == 4 and jobs[ci.PREPARE_JOB]["timeout-minutes"] == 20
    command = shlex.split(next(line for line in step["run"].replace("\\\n", "").splitlines() if line.startswith("env -u ")))
    assert command[:15] == ["env", "-u", "GITHUB_TOKEN", "-u", "GH_TOKEN", "-u", "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "-u", "ACTIONS_ID_TOKEN_REQUEST_URL", "-u", "ACTIONS_RUNTIME_TOKEN", "timeout", "--signal=KILL", "180s", "${retention_first_command[@]}"]
    assert command[command.index("--expected-producer-source") + 1] == budget.PRODUCER_SOURCE
    assert command[command.index("--expected-request-sha256") + 1] == budget.REQUEST_SHA256
    assert command[command.index("--cell-id") + 1] == budget.CELL_ID
    assert command[command.index("--expected-reader-sha256") + 1] == "$retention_reader_sha"
    assert "stderr.log" not in step["run"].split("# Only the reviewed reader")[1]
    assert 'tee -a "$GITHUB_STEP_SUMMARY" < "$retention_result_parent/receipt.json"' in step["run"]
    assert all("codex_retention_first_cell_budget.py" not in item.get("run", "")
               for job in (ci.APPROVE_JOB, ci.EXECUTE_JOB) for item in jobs[job]["steps"])
    assert not effects and all(not api.commits for api in transports)
    assert subprocess.Popen is not REAL_POPEN and subprocess.Popen.__name__ == socket.create_connection.__name__ == "blocked"
    with capsys.disabled():
        print(json.dumps({"scope": "synthetic_legacy_first_cell_result_only_budget", "new_profiles": 1,
            "closed_budget_profiles": 8, "mode_cases": mode_cases, "primary_terminal_before_dependencies": True,
            "legacy_optional_metadata_and_generation_preserved": True, "nonempty_deliverable_metadata_only": True,
            "new_full_intake_delivery_or_grade": False, "network_model_writer_child_paid_effects": 0,
            "actual_successful_keep_budget_values_supplied": False}, sort_keys=True))
