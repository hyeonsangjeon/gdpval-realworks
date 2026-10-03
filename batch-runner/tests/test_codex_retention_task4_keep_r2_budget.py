"""One offline proof for successful Task4 KEEP/r2 RESULT-only budget reading."""

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
# Established helper owners load at collection, before the offline guards.
from .test_codex_retention_ci import REAL_POPEN
from . import test_codex_retention_ci_observation as workflow_contract
from . import test_codex_retention_fresh_r1_result_intake as fixtures
from .test_codex_retention_task5_fresh_r1_read import _task5_fixture, TASK5_FILE
from .test_codex_retention_task5_r1_budget import _assert_task5_r1_observations
from .test_codex_retention_task4_fresh_budget import _assert_task4_fresh_observations
from .test_codex_retention_result_intake import FILE, PRIVATE

ci, retained, output, owned, intake = reader.ci, reader.retained, reader.output, reader.owned, reader.intake


def test_task4_keep_r2_success_budget_is_fixed_private_and_model_free(tmp_path, monkeypatch, capsys):
    effects, transports, failures = [], [], []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("KEEP/r2 budget proof crossed a live, paid, child, writer or full-payload boundary")

    producers = (fresh_r1, fresh_r2, keep_r2, task5_fresh_r1, task5_keep_r1, task5_keep_r2, task5_fresh_r2)
    ordinary_intake = reader.read_result
    for owner, names in (
        (ci, ("execute", "verify_approval", "verify_job_origin", "verify_terminal")),
        *((producer, ("execute", "_predecessor", "verify_terminal")) for producer in producers),
        *((admission, ("__init__",)) for admission in (
            fresh_r1._FreshAdmission, fresh_r2._FreshR2Admission, keep_r2._KeepR2Admission,
            task5_fresh_r1._Task5FreshR1Admission, task5_keep_r1._Task5KeepR1Admission,
            task5_keep_r2._Task5KeepR2Admission, task5_fresh_r2._Task5FreshR2Admission, ci._Admission)),
        (ci.LocalTransport, ("github_job_token", "authority_opener", "github", "azure")),
        (owned.LocalTransport, ("clock", "child", "process")),
        (ci.preparation, ("prepare_packet", "verify_packet")), (ci.historical, ("observe",)),
        (ci.controller, ("execute_first_cell", "stage_runtime", "_deadline")),
        (CodexTaskDeadlineStore, ("__init__",)), (CodexTaskDeadline, ("admit_attempt",)),
        (intake.retained_reader, ("prepare", "main")), (output, ("_hf_client", "publish")),
        (observer.bridge, ("prepare", "claim", "judge", "publish", "reconcile")),
        (observer.readout, ("main",)), (fixtures.FreshResultHF, ("create_commit", "list_repo_tree")),
        (reader, ("read_result", "bind_deliverable_file_records")),
        (intake, ("_payload", "bind_deliverable_file_records")),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    assert subprocess.Popen is not REAL_POPEN and subprocess.Popen.__name__ == "blocked"
    assert socket.create_connection.__name__ == socket.socket.connect.__name__ == "blocked"

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
            failures.append(chain)  # Safe original boundary, never private exception text.
            raise

    monkeypatch.setattr(reader, "observe_terminal", observed)
    profiles = (
        (reader.KEEP_R2, keep_r2, "KEEP_R2_BUDGET_CONTROLS",
         "retention-task4-keep-r2-budget-observation-v1", "retention-task4-keep-r2-budget-observation.json",
         "307dc07923d377faa7d7c6bd6c4934de2fa5f99e9007dd0d723f3c3337e6d010"),
        (reader.FRESH_R1, fresh_r1, "FRESH_R1_BUDGET_CONTROLS",
         "retention-task4-fresh-r1-budget-observation-v1", "retention-task4-fresh-r1-budget-observation.json",
         "5993b6d0c94ef1d56e808fab07941daed6e77d3f7adf7e055d9329043af63e02"),
        (reader.FRESH_R2, fresh_r2, "FRESH_R2_BUDGET_CONTROLS",
         "retention-task4-fresh-r2-budget-observation-v1", "retention-task4-fresh-r2-budget-observation.json",
         "7148453eb16dd8a0c6737bffe2fc5df42319dbb1a11afba2cdc2b90b649f305d"),
        (reader.TASK5_FRESH_R1, task5_fresh_r1, "TASK5_FRESH_R1_BUDGET_CONTROLS",
         "retention-task5-fresh-r1-budget-observation-v1", "retention-task5-fresh-r1-budget-observation.json",
         "d67cbfeb3a26716d445b36a4466d5dc55559652381db71056aaf44a50a43e2eb"),
        (reader.TASK5_KEEP_R1, task5_keep_r1, "TASK5_KEEP_R1_BUDGET_CONTROLS",
         "retention-task5-keep-r1-budget-observation-v1", "retention-task5-keep-r1-budget-observation.json",
         "4c75e2f0d8eb5a197fc44c2dc71b1abc166334c350791224ab5e3abc1a017cc3"),
        (reader.TASK5_KEEP_R2, task5_keep_r2, "TASK5_KEEP_R2_BUDGET_CONTROLS",
         "retention-task5-keep-r2-budget-observation-v1", "retention-task5-keep-r2-budget-observation.json",
         "1bda6431161ff4d27e751b3475979f861eb875beb7d16a608c7649830f051286"),
        (reader.TASK5_FRESH_R2, task5_fresh_r2, "TASK5_FRESH_R2_BUDGET_CONTROLS",
         "retention-task5-fresh-r2-budget-observation-v1", "retention-task5-fresh-r2-budget-observation.json",
         "3dd0af0802619dd60cc9eda5c492f6b75cd641463dca84a68ad5ad362e56074a"),
    )
    controls = {name: deepcopy(getattr(reader, name)) for _, _, name, *_ in profiles}
    readout = json.loads((ci.ROOT / "tasks/codex_budget_pilot/retention_diagnostic_readout.json").read_bytes())
    plan = intake.registration.compile_plan()
    for profile, producer, name, _, _, config_hash in profiles:
        row, fixed = readout["cells"][profile.ordinal], controls[name]
        expected = {
            "terminal_commit": row["terminal"]["revision"],
            "terminal_identity": {"sha256": row["terminal"]["sha256"], "size": row["terminal"]["bytes"]},
            "claim_commit": row["claim"]["revision"],
            "claim_identity": {"sha256": row["claim"]["sha256"], "size": row["claim"]["bytes"]},
            "output_commit": row["output_manifest"]["revision"],
            "output_manifest_identity": {"sha256": row["output_manifest"]["sha256"], "size": row["output_manifest"]["bytes"]},
            "output_objects_sha256": row["output_objects_sha256"],
            "status": "succeeded" if profile is reader.KEEP_R2 else "failed",
            "exit_code": 0 if profile is reader.KEEP_R2 else 1, "cleanup_confirmed": True}
        if profile is reader.FRESH_R1 or profile is reader.FRESH_R2:
            assert "retained_authority_sha256" not in row["read"]
        else:
            expected["retained_authority_sha256"] = row["read"]["retained_authority_sha256"]
        assert fixed == expected
        assert profile.expectation == ci.TerminalExpectation(
            row["producer"]["request_sha256"], row["producer"]["source_sha"], row["cell_id"])
        assert (profile.run_id, profile.execution_job_id, row["producer"]["attempt"]) == (
            row["producer"]["run_id"], row["producer"]["execution_job_id"], 1)
        assert (profile.retention_bundle, profile.repetition) == (row["retention_bundle"], row["repetition"])
        assert producer.PREDECESSOR["terminal_commit"] == row["preceding_registered_inference_terminal"]
        cell = intake.controller._adapted_cell(plan["cells"][profile.ordinal])
        assert cell["config_sha256"] == intake.registration.seal(cell["config"]) == config_hash
    assert reader.KEEP_R2_CONFIG_SHA256 == profiles[0][-1]
    assert reader.KEEP_R2_BUDGET_FORMAT == profiles[0][3] and reader.KEEP_R2_BUDGET_MARKER == profiles[0][4]
    assert reader.TASK5_KEEP_R1.materialized_grader_source_sha256 is None
    _assert_task4_fresh_observations(readout)
    _assert_task5_r1_observations(readout)
    historical_grade = deepcopy(readout["cells"][3]["grade"])
    assert (historical_grade["score"], historical_grade["included_max"], historical_grade["included_percent"],
            historical_grade["full_percent"]) == ("30.35", "45", "67.44", "54.20")
    assert readout["cells"][3]["read"]["successful_intake_established"] is True
    assert "current_budget_observation" not in readout["cells"][3]
    assert hashlib.sha256((ci.ROOT / "tasks/codex_budget_pilot/REPORT.md").read_bytes()).hexdigest() == (
        "88a37d8cfdae6c3c05a79db78827bfe2d59fdcd944067e4f6fcd7f387dddae0e")
    report = (ci.ROOT / "tasks/codex_budget_pilot/RETENTION_DIAGNOSTIC_REPORT.md").read_text()
    assert "Both successful Task4 KEEP budgets remain unobserved" in " ".join(report.split())
    for index in (1, 2, 4, 5, 6, 7):
        actual = readout["cells"][index]["current_budget_observation"]
        for value in actual["inference_budget_snapshot"].values():
            if type(value) in (int, float):
                assert str(value) in report
        assert actual["marker_sha256"] in report and actual["result"]["sha256"] in report
    with capsys.disabled():
        print("BOUNDARY exact seven configurations/controls; two actual FRESH additions restore delivered JSON when removed; grades/pilot unchanged")

    source = reader.reader_identity(binding=reader.KEEP_R2)
    monkeypatch.setattr(intake.registration, "compile_plan", lambda: deepcopy(plan))
    receipt = ci.project_cost_receipt(CostReceipt(status="partial", model_calls=1,
        known_cost_usd=Decimal("0.01"), model_cost_usd=Decimal("0.01"),
        usage={"input_tokens": 12, "cached_input_tokens": 8, "output_tokens": 3, "reasoning_tokens": 2},
        missing_reasons=("synthetic_missing_cost",)).as_dict())
    fields = ("total_seconds", "started_unix", "expires_unix", "remaining_seconds",
              "wait_seconds", "attempts_admitted", "native_resumes")
    second_file = FILE.rsplit("/", 1)[0] + "/second.txt"
    download = fixtures.FreshResultHF.hf_hub_download

    def bounded_download(api, **kwargs):
        control_paths = [api.producer.TERMINAL, api.producer.CLAIM, api.producer.OUTPUT + "/" + output.MANIFEST]
        result_path = api.producer.OUTPUT + "/" + intake.RESULT
        assert kwargs["filename"] in {*control_paths, result_path}, "ledger/deliverable body forbidden"
        if kwargs["filename"] == result_path:
            assert kwargs["revision"] == api.fixed["output_commit"]
            assert [name for _, name in api.downloads] == control_paths
        return download(api, **kwargs)

    monkeypatch.setattr(fixtures.FreshResultHF, "hf_hub_download", bounded_download)

    def revisions(fixed):
        monkeypatch.setattr(fixtures, "CLAIM_HEAD", fixed["claim_commit"])
        monkeypatch.setattr(fixtures, "OUTPUT_HEAD", fixed["output_commit"])

    def pin_controls(api):
        api.expected = {**api.fixed,
            "terminal_identity": owned._identity(retained._encoded(api.terminal)),
            "claim_identity": owned._identity(retained._encoded(api.claim)),
            "output_manifest_identity": owned._identity(retained._encoded(api.summary)),
            "output_objects_sha256": owned._digest(api.terminal["output_objects"])}
        if "retained_authority_sha256" in api.fixed:
            api.expected["retained_authority_sha256"] = owned._digest(api.terminal["authority"])

    def seal(api):
        revisions(api.fixed)
        api.bind_payload()
        api.seed()
        pin_controls(api)

    def complete(profile):
        cell = intake.controller._adapted_cell(plan["cells"][profile.ordinal])
        return {"run_id": cell["run_id"], "task_id": cell["task_id"], **cell["control"],
            "total_seconds": 10800, "attempt_seconds": 1800, "started_unix": 100.0, "expires_unix": 10900.0,
            "remaining_seconds": 100.0, "wait_seconds": 12.5, "attempts_admitted": 2,
            "native_resumes": 1 if profile.retention_bundle == "keep" else 0}

    default_snapshot = object()

    def make(profile=reader.KEEP_R2, snapshot=default_snapshot):
        spec = next(spec for spec in profiles if spec[0] is profile)
        fixed = controls[spec[2]]
        revisions(fixed)
        task4 = profile in (reader.FRESH_R1, reader.FRESH_R2, reader.KEEP_R2)
        # Reuse each task's established source fixture owner, with no role overwrite.
        factory = fixtures.FreshResultHF if task4 else _task5_fixture
        api = factory(plan, binding=profile, receipt=receipt, with_ledger=True, terminal_head=fixed["terminal_commit"])
        transports.append(api)
        api.fixed, api.profile, api.spec = fixed, profile, spec
        api.claim["authority"]["provider_job_id"] = profile.execution_job_id
        api.terminal["authority"] = deepcopy(api.claim["authority"])
        api.payload["condition"] = plan["cells"][profile.ordinal]["config"]["condition_a"]["name"]
        row = api.payload["results"][0]
        row["observability"] = {"task_deadline": deepcopy(complete(profile) if snapshot is default_snapshot else snapshot)}
        if profile is reader.KEEP_R2:
            api.files[second_file] = b"x"  # One-byte metadata exercises bool-versus-int size rejection.
            row.update(deliverable_files=[FILE, second_file], deliverable_file_records=[
                {"path": name, **owned._identity(api.files[name])} for name in (FILE, second_file)])
        else:
            api.files.pop(FILE if task4 else TASK5_FILE)
            row.update(status="error", deliverable_files=[], deliverable_file_records=[])
            api.summary.update(status="failed", exit_code=1)
        api.terminal.update(claim_commit=fixed["claim_commit"], output_commit=fixed["output_commit"])
        seal(api)
        return api

    def options(api, name, **changes):
        return {"expectation": api.profile.expectation, "binding": api.profile, "destination": tmp_path / name,
            "expected_reader_sha256": source["module_sha256"], "terminal_revision": api.fixed["terminal_commit"],
            "include_budget": True, "_test_api": api, **changes}

    def read(api, name, **changes):
        revisions(api.fixed)
        with monkeypatch.context() as synthetic:
            synthetic.setattr(reader, api.spec[2], api.expected)
            return reader.observe_terminal(**options(api, name, **changes))

    def refuse(api, name, *, before_result=False, **changes):
        with pytest.raises((OSError, ValueError, TypeError, KeyError)):
            read(api, name, **changes)
        assert all(not (tmp_path / name / spec[4]).exists() for spec in profiles)
        if before_result:
            assert all(path != api.producer.OUTPUT + "/" + intake.RESULT for _, path in api.downloads)

    def captured(api):
        text = capsys.readouterr()
        assert not text.err
        assert all(secret not in text.out for secret in
            (str(tmp_path), api.repo, TOKEN, PRIVATE.decode().strip(), FILE, second_file, TASK5_FILE, "SECRET-LIKE-ERROR"))
        return json.loads(text.out)

    def cli(api, name):
        revisions(api.fixed)
        profile = api.profile
        with monkeypatch.context() as synthetic:
            synthetic.setattr(reader, api.spec[2], api.expected)
            code = reader.main(["--observe-budget", "--terminal-revision", api.fixed["terminal_commit"],
                "--expected-producer-source", profile.expectation.source_sha,
                "--expected-request-sha256", profile.expectation.request_sha256,
                "--cell-id", profile.expectation.cell_id, "--expected-reader-sha256", source["module_sha256"],
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
        wrong_profiles = (*(spec[0] for spec in profiles[1:]), replace(reader.KEEP_R2),
            replace(reader.KEEP_R2, run_id="1"), replace(reader.KEEP_R2, execution_job_id=1), object())
        for index, changes in enumerate((
            *({"binding": other} for other in wrong_profiles), {"include_budget": 1},
            {"expected_reader_sha256": "c" * 64}, {"expectation": intake.EXPECTATION},
            {"expectation": replace(reader.KEEP_R2.expectation, cell_id="unknown")},
            {"expectation": replace(reader.KEEP_R2.expectation, source_sha="a" * 40)},
            {"expectation": replace(reader.KEEP_R2.expectation, request_sha256="b" * 64)},
            {"terminal_revision": keep_r2.PREDECESSOR["terminal_commit"]},
            {"terminal_revision": None, "discover_terminal": True},
        )):
            name = "early-" + str(index)
            refuse(api, name, before_result=True, **changes)
            assert not (tmp_path / name).exists()
        for index, mutation in enumerate((
            lambda value: value["cells"][3].update(config_sha256=reader.TASK5_KEEP_R2_CONFIG_SHA256),
            lambda value: value["cells"][3]["config"]["execution"].update(timeout=1801),
        )):
            wrong = deepcopy(plan)
            mutation(wrong)
            early.setattr(intake.registration, "compile_plan", lambda: wrong)
            refuse(api, "sealed-config-" + str(index), before_result=True)
    real_bytes, real_import = output._bytes, builtins.__import__
    for bad_path in (Path(reader.__file__), *(Path(path) for path, _ in reader._frozen(reader.KEEP_R2).values()),
                     reader.BUDGET_PROJECTOR_PIN[0]):
        for missing in (False, True):
            def changed(path, **kwargs):
                if Path(path) == bad_path:
                    if missing:
                        raise FileNotFoundError("synthetic missing current source")
                    return real_bytes(path, **kwargs) + b"\n"
                return real_bytes(path, **kwargs)

            def no_import(name, *args, **kwargs):
                guarded = "codex_budget_pilot_grade_readout" if bad_path == reader.BUDGET_PROJECTOR_PIN[0] else keep_r2.__name__
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
        print("BOUNDARY exact successful KEEP/r2 only; first KEEP/r1/unknown/copied identities and changed/missing pins refused before credentials/import")

    monkeypatch.setenv("HF_TOKEN", TOKEN)  # Authored fixture token, never a credential.
    api = make()
    code, record = cli(api, "success-budget")
    assert code == 0, {"boundary": "first_success_result_only_budget", "original_causes": failures[-1:]}
    assert record["format"] == reader.KEEP_R2_BUDGET_FORMAT and record["mode"] == "observe_budget"
    assert record["inference_budget_snapshot"] == {**{key: complete(reader.KEEP_R2)[key] for key in fields}, "missing": {}}
    assert record["result"] == {**owned._identity(api.files[intake.RESULT]),
        "result_fingerprint": api.payload["result_fingerprint"],
        "recorded_prepared_fingerprint": api.payload["prepared_fingerprint"],
        "registered_config_sha256": reader.KEEP_R2_CONFIG_SHA256}
    assert record["predecessor"] == keep_r2.PREDECESSOR and record["supplied_request_binding"] == reader._request_context(reader.KEEP_R2)
    assert record["expected_execution_job_id"] == record["recorded_provider_job_id"] == reader.KEEP_R2.execution_job_id
    assert (record["status"], record["exit_code"], record["cleanup_confirmed"], record["grade"]) == ("succeeded", 0, True, None)
    assert record["result_body_verified"] is True and record["payload_verification_scope"] == "inference_result_only"
    for key in ("payload_bodies_verified", "ledger_body_verified", "deliverable_bodies_verified", "grading_input_ready",
                "fresh_origin_authentication", "prepared_input_independently_verified", "git_parent_cas_independently_verified",
                "launch_authorized", "grading_launched", "admission_attempted", "replay_authorized", "invoice_complete",
                "full_intake_established_by_this_observation", "delivery_established_by_this_observation",
                "grade_established_by_this_observation"):
        assert record[key] is False
    assert not {"intake_verified", "results", "raw_payload", "stderr", "error", "deliverable_files"} & record.keys()
    assert record["writer_acknowledgment"] == "not_established" and record["recorded_publication_acknowledged"] is True
    assert record["receipt"] == receipt and record["commands"] == []
    assert record["declared_payload_roles"] == {"inference_result": 1, "ledger": 1, "deliverables": 2}
    assert record["declared_output_object_count"] == 5
    assert record["retained_authority_sha256"] == owned._digest(api.terminal["authority"])
    assert set(record["unavailable"]) == {"detailed_failure", "recovery_exposure"}
    result_path = keep_r2.OUTPUT + "/" + intake.RESULT
    assert api.downloads == [(api.fixed["terminal_commit"], keep_r2.TERMINAL), (api.fixed["claim_commit"], keep_r2.CLAIM),
        (api.fixed["output_commit"], keep_r2.OUTPUT + "/" + output.MANIFEST), (api.fixed["output_commit"], result_path)]
    assert len(api.payload["results"][0]["deliverable_file_records"]) == 2
    assert all(revision != retained.BRANCH for revision, _ in api.path_reads)
    marker = tmp_path / "success-budget" / reader.KEEP_R2_BUDGET_MARKER
    marker_bytes, calls = marker.read_bytes(), deepcopy(api.calls)
    assert marker.stat().st_mode & 0o777 == 0o600 and marker.parent.stat().st_mode & 0o777 == 0o700
    assert record["observation_sha256"] == owned._identity(marker_bytes)["sha256"]
    assert all(not (marker.parent / spec[4]).exists() for spec in profiles[1:])
    with pytest.raises(output.OutputPublicationRefused, match="^new_result_destination_required$"):
        read(api, "success-budget")
    assert api.calls == calls and marker.read_bytes() == marker_bytes

    for index, mutation in enumerate((
        lambda item: item.terminal["authority"].update(provider_run_id=reader.TASK5_KEEP_R2.run_id),
        lambda item: item.terminal["authority"].update(provider_job_id=reader.TASK5_KEEP_R2.execution_job_id),
        lambda item: item.summary.update(source_sha=reader.TASK5_KEEP_R2.expectation.source_sha),
        lambda item: item.summary.update(cell_id=reader.TASK5_KEEP_R2.expectation.cell_id),
        lambda item: item.terminal.update(request_sha256=reader.TASK5_KEEP_R2.expectation.request_sha256),
        lambda item: item.claim.update(expected_parent=item.fixed["terminal_commit"]),
        lambda item: item.claim["predecessor"].update(cell_id="wrong-predecessor"),
        lambda item: item.summary.update(cleanup_confirmed=False),
        lambda item: item.summary.update(status="failed", exit_code=1),
        lambda item: item.summary.update(exit_code=1),
        lambda item: item.terminal.update(publication_acknowledged=False),
    )):
        bad = make()
        mutation(bad)
        seal(bad)
        refuse(bad, "control-" + str(index), before_result=True)
    for key in ("terminal_identity", "claim_identity", "output_manifest_identity"):
        for field in ("sha256", "size"):
            bad = make()
            bad.expected[key][field] = "0" * 64 if field == "sha256" else bad.expected[key][field] + 1
            refuse(bad, key + field, before_result=True)
    for key in ("output_objects_sha256", "retained_authority_sha256"):
        bad = make()
        bad.expected[key] = "0" * 64
        refuse(bad, key, before_result=True)
    for index, (revision, path) in enumerate((
        (api.fixed["claim_commit"], keep_r2.CLAIM), (api.fixed["output_commit"], result_path),
        (api.fixed["terminal_commit"], keep_r2.OUTPUT + "/" + intake.LEDGER),
        (api.fixed["output_commit"], keep_r2.OUTPUT + "/" + FILE),
    )):
        bad = make()
        bad.writers[revision][path] = "f" * 40
        refuse(bad, "history-" + str(index), before_result=True)
    # Canonical/path/schema/size/hash metadata is validated before the RESULT.
    for index, wrong_name in enumerate((FILE.replace(intake.registration.TASK4, intake.registration.TASK5),
                                        FILE.replace("report.txt", "../report.txt"),
                                        FILE.replace("report.txt", "state.sqlite"))):
        bad = make()
        bad.files[wrong_name] = bad.files.pop(FILE)
        seal(bad)
        refuse(bad, "manifest-path-" + str(index), before_result=True)
    for index, mutation in enumerate((
        lambda value: value.update(size=True), lambda value: value.update(size=-1),
        lambda value: value.update(sha256="not-a-hash"), lambda value: value.update(extra="not-a-field"),
    )):
        bad = make()
        mutation(next(value for value in bad.summary["files"] if value["path"] == second_file))
        # Keep the three control bodies mutually consistent, but not valid.
        manifest = retained._encoded(bad.summary)
        name = keep_r2.OUTPUT + "/" + output.MANIFEST
        bad.terminal["output_objects"] = [retained._object(name, manifest) if value["path"] == name else value
                                           for value in bad.terminal["output_objects"]]
        bad.trees[bad.fixed["output_commit"]][name] = manifest
        bad.trees[bad.fixed["terminal_commit"]][name] = manifest
        bad.trees[bad.fixed["terminal_commit"]][keep_r2.TERMINAL] = retained._encoded(bad.terminal)
        pin_controls(bad)
        refuse(bad, "manifest-metadata-" + str(index), before_result=True)

    bad = make()
    bad.corrupt = result_path
    refuse(bad, "result-size-hash")
    for index, mutation in enumerate((
        lambda value: value.update(source="synthetic-wrong/source"),
        lambda value: value.update(run_id="wrong-config-run"),
        lambda value: value.update(condition="wrong-condition"),
        lambda value: value.update(ordered_task_ids=[intake.registration.TASK5]),
        lambda value: value["results"][0].update(task_id=intake.registration.TASK5),
        lambda value: value["results"][0].update(status="error"),
        lambda value: value["results"][0].update(problem_solving_cost=None),
        lambda value: value["results"][0].update(deliverable_files=[]),
        lambda value: value["results"][0].update(deliverable_files=[FILE, FILE]),
        lambda value: value["results"][0].update(deliverable_files=[FILE, "../second.txt"]),
        lambda value: value["results"][0].update(deliverable_file_records=[]),
        lambda value: value["results"][0]["deliverable_file_records"].reverse(),
        lambda value: value["results"][0]["deliverable_file_records"][1].update(size=True),
        lambda value: value["results"][0]["deliverable_file_records"][1].update(size=2),
        lambda value: value["results"][0]["deliverable_file_records"][0].update(sha256="0" * 64),
        lambda value: value["results"][0]["deliverable_file_records"][0].update(extra=1),
        lambda value: value["results"][0]["deliverable_file_records"][0].update(path=TASK5_FILE),
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
        assert bad.downloads[-1] == (bad.fixed["output_commit"], result_path)
    bad = make()
    bad.payload["result_fingerprint"] = "0" * 64
    bad.files[intake.RESULT] = (json.dumps(bad.payload, sort_keys=True) + "\n").encode()
    bad.seed()
    pin_controls(bad)
    refuse(bad, "fingerprint")
    absent = make(snapshot={})
    del absent.payload["results"][0]["observability"]
    seal(absent)
    assert read(absent, "absent")["inference_budget_snapshot"] == {
        **dict.fromkeys(fields), "missing": dict.fromkeys(fields, "not_recorded")}
    nullable = make(snapshot={"total_seconds": 10800, "remaining_seconds": None})
    assert read(nullable, "nullable")["inference_budget_snapshot"] == {
        "total_seconds": 10800, **dict.fromkeys(fields[1:]), "missing": {
            **dict.fromkeys(fields[1:], "not_recorded"), "remaining_seconds": "unavailable"}}
    zeros = make(snapshot={"total_seconds": 10800, **dict.fromkeys(fields[1:], 0)})
    assert read(zeros, "zeros")["inference_budget_snapshot"] == {
        "total_seconds": 10800, **dict.fromkeys(fields[1:], 0), "missing": {}}
    with capsys.disabled():
        print("BOUNDARY successful controls/history/authority sealed before RESULT; nonempty deliverable metadata only, tamper refusals and missing/null/zero")

    writer, real_bytes = reader._write_no_clobber, output._bytes
    for failure in ("write", "readback"):
        unresolved, name = make(), "lost-" + failure

        def lost_write(path, data, **kwargs):
            writer(path, data, **kwargs)
            if Path(path).name == reader.KEEP_R2_BUDGET_MARKER:
                raise OSError("SECRET-LIKE-ERROR lost marker acknowledgment")

        def lost_readback(path, **kwargs):
            if Path(path).name == reader.KEEP_R2_BUDGET_MARKER:
                raise OSError("SECRET-LIKE-ERROR lost marker readback")
            return real_bytes(path, **kwargs)

        with monkeypatch.context() as lost:
            if failure == "write":
                lost.setattr(reader, "_write_no_clobber", lost_write)
            else:
                lost.setattr(output, "_bytes", lost_readback)
            code, result = cli(unresolved, name)
            assert code == 2 and result["budget_observation_verified"] is False
            assert result["reason"] == "fresh_terminal_observation_unconfirmed"
        assert (tmp_path / name / reader.KEEP_R2_BUDGET_MARKER).is_file()
        calls = deepcopy(unresolved.calls)
        code, result = cli(unresolved, name)
        assert code == 2 and not result["budget_observation_verified"] and unresolved.calls == calls
    bad = make()
    bad.read_error = OSError("SECRET-LIKE-ERROR " + str(tmp_path))
    code, result = cli(bad, "private-error")
    assert code == 2 and result["reason"] == "fresh_budget_observation_refused"
    successful_controls = make()
    with monkeypatch.context() as no_budget:
        no_budget.setattr(reader, "_budget_projector", forbidden)
        with pytest.raises(output.OutputPublicationRefused, match="^fresh_terminal_unsuccessful_required$"):
            read(successful_controls, "success-not-terminal-only", include_budget=False)
    assert len(successful_controls.downloads) == 1

    # Fresh synthetic observations exercise each existing path, not an old test
    # or a replay of any consumed real budget observation.
    for profile, _, _, expected_format, marker_name, config_hash in profiles[1:]:
        prefix, api = "compat-" + str(profile.ordinal) + "-", make(profile)
        record = read(api, prefix + "budget")
        assert record["format"] == expected_format and record["result"]["registered_config_sha256"] == config_hash
        assert record["inference_budget_snapshot"] == {**{key: complete(profile)[key] for key in fields}, "missing": {}}
        assert (tmp_path / (prefix + "budget") / marker_name).is_file()
        assert (record["status"], record["exit_code"], record["cleanup_confirmed"], record["grade"]) == ("failed", 1, True, None)
        assert not any(key.endswith("_established_by_this_observation") for key in record)
        assert record["result_body_verified"] is True and record["payload_bodies_verified"] is False
        assert record["supplied_request_binding"] == reader._request_context(profile)
        old, other = make(profile), make(profile)
        with monkeypatch.context() as controls_only:
            controls_only.setattr(reader, "_budget_projector", forbidden)
            explicit = read(old, prefix + "controls-explicit", include_budget=False)
            arguments = options(other, prefix + "controls-default")
            del arguments["include_budget"]
            omitted = reader.observe_terminal(**arguments)
        assert explicit == omitted and explicit["outcome"] == "terminal_verified"
        assert "inference_budget_snapshot" not in explicit and explicit["unavailable"]["budget"]["reason"] == "not_recorded_in_terminal_controls"
        assert explicit["payload_bodies_verified"] is False and len(old.downloads) == len(other.downloads) == 3
        stopped = make(profile)
        stopped.summary.update(status="stopped", exit_code=None)
        seal(stopped)
        record = read(stopped, prefix + "stopped-controls", include_budget=False)
        assert record["status"] == "stopped" and record["grade"] is None and len(stopped.downloads) == 3
        stopped.downloads.clear()
        refuse(stopped, prefix + "not-fixed-failed", before_result=True)
        failed_intake = make(profile)
        with pytest.raises(output.OutputPublicationRefused, match="^fresh_result_success_required$"):
            ordinary_intake(**{key: value for key, value in options(failed_intake, prefix + "not-success").items()
                               if key != "include_budget"})
        assert all(path != api.producer.OUTPUT + "/" + intake.RESULT for _, path in failed_intake.downloads)
        declared = make(profile)
        task_file = FILE if profile in (reader.FRESH_R1, reader.FRESH_R2) else TASK5_FILE
        declared.files[task_file] = PRIVATE
        declared.payload["results"][0].update(deliverable_files=[task_file],
            deliverable_file_records=[{"path": task_file, **owned._identity(PRIVATE)}])
        seal(declared)
        refuse(declared, prefix + "failed-still-empty-deliverables", before_result=True)
    assert readout["cells"][3]["grade"] == historical_grade
    assert all(getattr(reader, name) == fixed for name, fixed in controls.items())
    for name, digest in observer.CURRENT_DEPENDENCIES.items():
        assert hashlib.sha256((ci.ROOT / "batch-runner" / name).read_bytes()).hexdigest() == digest
    assert observer.bridge.fixed_evidence_sha256() == "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d"
    assert observer.bridge.fixed_evidence_sha256("retention/keep-r2") == "25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0"
    assert observer.bridge._fixed("retention/keep-r2").RESULT["intake_sha256"] == "4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4"
    with capsys.disabled():
        print("BOUNDARY private no-clobber/readback/lost-ack/no-replay; six failed budgets and ordinary failed/stopped/intake refusals unchanged")

    workflow_contract._assert_retention_execution_workflow_contract()
    workflow_contract._assert_retention_mode_routes()
    workflow = yaml.safe_load((ci.ROOT / ci.WORKFLOW).read_bytes())
    jobs, cells = workflow["jobs"], tuple(plan["order"])
    steps = jobs[ci.PREPARE_JOB]["steps"]
    budget_cells = set(cells)
    assert len(workflow_contract._BUDGET_CELLS) == 8 and set(workflow_contract._BUDGET_CELLS) == budget_cells
    names = ("prepare", "execute", "observe_locator", "read_result", "observe_terminal", "observe_budget")
    mode_cases = 0
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
        mode_cases += 1
    assert mode_cases == 576
    preflight, step = steps[13:15]
    terminal_cells = " && (" + " || ".join("inputs.cell_id == '" + cell + "'" for cell in cells[1:]) + ")"
    assert preflight["if"] == step["if"] == workflow_contract._terminal_observation_condition() + terminal_cells
    assert "secrets." not in preflight["run"] and '"$(git rev-parse HEAD)" == "$REVIEWED_SOURCE_SHA"' in preflight["run"]
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
    assert workflow_contract._budget_terminal_selection() in step["run"]
    assert "retention_terminal_args=(--observe-terminal --discover-terminal)" in step["run"]
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
        print(json.dumps({"scope": "synthetic_task4_keep_r2_success_result_only_budget", "new_profiles": 1,
            "closed_budget_profiles": 8, "mode_cases": mode_cases, "successful_controls_before_result": True,
            "nonempty_deliverable_metadata_only": True, "new_intake_delivery_or_grade_established": False,
            "six_failed_budget_paths_unchanged": True, "missing_null_zero_preserved": True,
            "private_marker_readback_no_replay": True, "current_historical_pins_separate": True,
            "two_actual_task4_fresh_observations_separate": True, "prior_json_grade_and_pilot_unchanged": True,
            "successful_task4_keep_budgets_unobserved": True, "network_model_writer_child_paid_effects": len(effects)}, sort_keys=True))
