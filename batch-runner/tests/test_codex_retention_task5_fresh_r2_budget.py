"""One offline proof of a fixed RESULT-only budget observation, never a live read."""

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
import codex_retention_task5_fresh_r2 as producer
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from core.cost_receipts import CostReceipt
from .test_codex_budget_pilot_retention import TOKEN, offline  # noqa: F401
# These helpers capture Popen at collection, before the unchanged offline fixture.
from .test_codex_retention_ci import REAL_POPEN
from . import test_codex_retention_ci_observation as workflow_contract
from . import test_codex_retention_fresh_r1_result_intake as fixtures
from .test_codex_retention_task5_fresh_r1_read import _task5_fixture, TASK5_FILE
from .test_codex_retention_result_intake import PRIVATE
from .retention_budget_report_evidence import before_success_budget_observations

ci, retained, output, owned, intake = reader.ci, reader.retained, reader.output, reader.owned, reader.intake


def test_final_task5_budget_observation_is_fixed_private_and_model_free(tmp_path, monkeypatch, capsys):
    effects, transports, failures = [], [], []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("budget observation crossed a live, paid, writer or child boundary")

    for owner, names in (
        (ci, ("execute", "verify_approval", "verify_job_origin", "verify_terminal")),
        (producer, ("execute", "_predecessor", "verify_terminal")),
        (producer._Task5FreshR2Admission, ("__init__",)), (ci._Admission, ("__init__",)),
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

    # Keep relative frames if a CLI refusal masks an unexpected failure, not its
    # private message, payload, path or credentials. Re-raise the original cause.
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
    binding = reader.TASK5_FRESH_R2
    fixed = deepcopy(reader.TASK5_FRESH_R2_BUDGET_CONTROLS)
    readout = json.loads((ci.ROOT / "tasks/codex_budget_pilot/retention_diagnostic_readout.json").read_bytes())
    row = readout["cells"][7]
    prior = before_success_budget_observations(readout)
    # Then remove the six earlier additions for this original historical scope.
    for index in (1, 2, 4, 5, 6, 7):
        prior["cells"][index].pop("current_budget_observation")
    canonical = (json.dumps(prior, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    assert hashlib.sha256(canonical).hexdigest() == "aaea03354686ada4e716b4eb0eb24b9c1ab964d8e4e4e4210e5b960519dfdd89"
    assert binding.expectation == ci.TerminalExpectation(
        "797141f8291078b82cf0d7a31c20fdadb5105bd0ad45d58f1225b8a39658c05a",
        "dfa812a2b7ad10b1aa3c7e873b4fabef9b195bd6",
        "0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_fresh_r2")
    assert (binding.ordinal, binding.repetition, binding.retention_bundle, binding.run_id,
            binding.execution_job_id) == (7, 2, "fresh", "37101934436", 111147701025)
    assert row["producer"] == {**row["producer"], "source_sha": binding.expectation.source_sha,
        "run_id": binding.run_id, "attempt": 1, "execution_job_id": binding.execution_job_id,
        "request_sha256": binding.expectation.request_sha256, "workflow_id": reader.EXPECTED_PROVIDER["workflow_id"]}
    assert fixed == {
        "terminal_commit": row["terminal"]["revision"],
        "terminal_identity": {"sha256": row["terminal"]["sha256"], "size": row["terminal"]["bytes"]},
        "claim_commit": row["claim"]["revision"],
        "claim_identity": {"sha256": row["claim"]["sha256"], "size": row["claim"]["bytes"]},
        "output_commit": row["output_manifest"]["revision"],
        "output_manifest_identity": {"sha256": row["output_manifest"]["sha256"], "size": row["output_manifest"]["bytes"]},
        "output_objects_sha256": row["output_objects_sha256"],
        "retained_authority_sha256": row["read"]["retained_authority_sha256"],
        "status": "failed", "exit_code": 1, "cleanup_confirmed": True}
    assert producer.PREDECESSOR["terminal_commit"] == row["preceding_registered_inference_terminal"] == (
        "3be1c0b892a199fdfccf3d5c4379d40c782119e5")
    assert binding.materialized_grader_source_sha256 == row["supplied_materialized_grader_source_sha256"]
    assert reader.TASK5_KEEP_R1.materialized_grader_source_sha256 is None
    source = reader.reader_identity(binding=binding)
    plan = intake.registration.compile_plan()
    cell = intake.controller._adapted_cell(plan["cells"][7])
    assert cell["config_sha256"] == intake.registration.seal(cell["config"]) == reader.TASK5_FRESH_R2_CONFIG_SHA256
    monkeypatch.setattr(intake.registration, "compile_plan", lambda: deepcopy(plan))

    # Reuse the existing synthetic writer's exclusive source/cache ownership.
    # Only its transport revision labels change; no source file is recreated.
    monkeypatch.setattr(fixtures, "CLAIM_HEAD", fixed["claim_commit"])
    monkeypatch.setattr(fixtures, "OUTPUT_HEAD", fixed["output_commit"])
    controls = {producer.TERMINAL, producer.CLAIM, producer.OUTPUT + "/" + output.MANIFEST}
    result_path = producer.OUTPUT + "/" + intake.RESULT
    receipt = ci.project_cost_receipt(CostReceipt(status="partial", model_calls=1,
        known_cost_usd=Decimal("0.01"), model_cost_usd=Decimal("0.01"),
        usage={"input_tokens": 12, "cached_input_tokens": 8, "output_tokens": 3, "reasoning_tokens": 2},
        missing_reasons=("synthetic_missing_cost",)).as_dict())
    complete = {"run_id": cell["run_id"], "task_id": cell["task_id"], **cell["control"],
        "total_seconds": 10800, "attempt_seconds": 1800, "started_unix": 100.0, "expires_unix": 10900.0,
        "remaining_seconds": 0.0, "wait_seconds": 12.5, "attempts_admitted": 2, "native_resumes": 0}
    fields = ("total_seconds", "started_unix", "expires_unix", "remaining_seconds",
              "wait_seconds", "attempts_admitted", "native_resumes")
    download = fixtures.FreshResultHF.hf_hub_download

    def bounded_download(api, **kwargs):
        assert kwargs["filename"] in controls | {result_path}, "ledger/deliverable body forbidden"
        if kwargs["filename"] == result_path:
            assert kwargs["revision"] == fixed["output_commit"]
            assert [name for _, name in api.downloads] == [producer.TERMINAL, producer.CLAIM,
                                                         producer.OUTPUT + "/" + output.MANIFEST]
        return download(api, **kwargs)

    monkeypatch.setattr(fixtures.FreshResultHF, "hf_hub_download", bounded_download)

    def seal(api):
        api.bind_payload()
        api.seed()
        api.expected = {**fixed,
            "terminal_identity": owned._identity(retained._encoded(api.terminal)),
            "claim_identity": owned._identity(retained._encoded(api.claim)),
            "output_manifest_identity": owned._identity(retained._encoded(api.summary)),
            "output_objects_sha256": owned._digest(api.terminal["output_objects"]),
            "retained_authority_sha256": owned._digest(api.terminal["authority"])}

    def make(snapshot=complete):
        api = _task5_fixture(plan, binding=binding, receipt=receipt, with_ledger=True,
                             terminal_head=fixed["terminal_commit"])
        transports.append(api)
        api.files.pop(TASK5_FILE)
        api.payload["condition"] = cell["config"]["condition_a"]["name"]
        api.payload["results"][0].update(status="error", deliverable_files=[], deliverable_file_records=[],
                                       observability={"task_deadline": deepcopy(snapshot)})
        api.summary.update(status="failed", exit_code=1)
        api.terminal.update(claim_commit=fixed["claim_commit"], output_commit=fixed["output_commit"])
        seal(api)
        return api

    def options(api, name, **changes):
        return {"expectation": binding.expectation, "binding": binding, "destination": tmp_path / name,
                "expected_reader_sha256": source["module_sha256"], "terminal_revision": fixed["terminal_commit"],
                "include_budget": True, "_test_api": api, **changes}

    def read(api, name, **changes):
        # Only authored synthetic control identities are substituted. Revisions,
        # independent provider binding and every real validator remain in force.
        with monkeypatch.context() as synthetic:
            synthetic.setattr(reader, "TASK5_FRESH_R2_BUDGET_CONTROLS", api.expected)
            return reader.observe_terminal(**options(api, name, **changes))

    def refuse(api, name, *, before_result=False, **changes):
        with pytest.raises((OSError, ValueError, TypeError, KeyError)):
            read(api, name, **changes)
        assert not (tmp_path / name / reader.BUDGET_MARKER).exists()
        if before_result:
            assert all(path != result_path for _, path in api.downloads)

    def captured(api):
        text = capsys.readouterr()
        assert not text.err
        assert all(secret not in text.out for secret in
            (str(tmp_path), api.repo, TOKEN, PRIVATE.decode().strip(), TASK5_FILE, "SECRET-LIKE-ERROR"))
        return json.loads(text.out)

    def cli(api, name):
        with monkeypatch.context() as synthetic:
            synthetic.setattr(reader, "TASK5_FRESH_R2_BUDGET_CONTROLS", api.expected)
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
        assert reader.main([], _test_api=api) == 0
        assert captured(api)["cell_id"] == reader.FRESH_R1.expectation.cell_id
        for other_mode in ("--read", "--observe-terminal"):
            assert reader.main(["--observe-budget", other_mode], _test_api=api) == 2
            assert captured(api)["reason"] == "invalid_arguments"
        for index, changes in enumerate((
            {"binding": replace(binding)}, {"binding": reader.TASK5_KEEP_R2}, {"include_budget": 1},
            {"expectation": replace(binding.expectation, cell_id=reader.TASK5_KEEP_R2.expectation.cell_id)},
            {"expectation": replace(binding.expectation, source_sha="a" * 40)},
            {"expectation": replace(binding.expectation, request_sha256="b" * 64)},
            {"expected_reader_sha256": "c" * 64}, {"terminal_revision": producer.PREDECESSOR["terminal_commit"]},
            {"terminal_revision": None, "discover_terminal": True},
        )):
            name = "early-" + str(index)
            refuse(api, name, before_result=True, **changes)
            assert not (tmp_path / name).exists()
        for index, mutation in enumerate((
            lambda value: value["cells"][7].update(config_sha256="0" * 64),
            lambda value: value["cells"][7]["config"]["execution"].update(timeout=1801),
        )):
            wrong = deepcopy(plan)
            mutation(wrong)
            early.setattr(intake.registration, "compile_plan", lambda: wrong)
            refuse(api, "config-" + str(index), before_result=True)
    assert not api.calls and not effects

    real_bytes, real_import = output._bytes, builtins.__import__
    for bad_path, _ in (*reader._frozen(binding).values(), reader.BUDGET_PROJECTOR_PIN):
        for missing in (False, True):
            def changed(path, **kwargs):
                if Path(path) == Path(bad_path):
                    if missing:
                        raise FileNotFoundError("synthetic missing current source")
                    return real_bytes(path, **kwargs) + b"\n"
                return real_bytes(path, **kwargs)

            def no_import(name, *args, **kwargs):
                guarded = ("codex_budget_pilot_grade_readout" if Path(bad_path) == reader.BUDGET_PROJECTOR_PIN[0]
                           else "codex_retention_task5_fresh_r2")
                if name == guarded:
                    return forbidden()
                return real_import(name, *args, **kwargs)

            with monkeypatch.context() as corrupt:
                corrupt.setattr(output, "_bytes", changed)
                corrupt.setattr(builtins, "__import__", no_import)
                corrupt.setattr(retained, "_session", forbidden)
                name = "pin-" + Path(bad_path).stem + str(missing)
                refuse(api, name, before_result=True)
                assert not (tmp_path / name).exists()
    assert not api.calls and not effects
    with capsys.disabled():
        print("BOUNDARY exact final binding/config/current pins: refusals precede lazy imports and private/session effects")

    monkeypatch.setenv("HF_TOKEN", TOKEN)  # Authored synthetic token, never a credential.
    code, record = cli(api, "budget")
    assert code == 0, {"boundary": "first_result_budget_projection", "original_causes": failures[-1:]}
    assert record["mode"] == "observe_budget" and record["budget_observation_verified"] is True
    assert record["terminal_verified"] is True and record["outcome"] == "budget_observation_verified"
    assert (record["status"], record["exit_code"], record["cleanup_confirmed"], record["grade"]) == ("failed", 1, True, None)
    assert record["inference_budget_snapshot"] == {**{key: complete[key] for key in fields}, "missing": {}}
    assert record["inference_budget_snapshot"]["attempts_admitted"] != record["receipt"]["model_calls"]
    assert record["result_body_verified"] is True and record["payload_verification_scope"] == "inference_result_only"
    for key in ("payload_bodies_verified", "ledger_body_verified", "deliverable_bodies_verified", "grading_input_ready",
                "fresh_origin_authentication", "prepared_input_independently_verified", "git_parent_cas_independently_verified",
                "launch_authorized", "grading_launched", "admission_attempted", "replay_authorized", "invoice_complete"):
        assert record[key] is False
    assert record["writer_acknowledgment"] == "not_established" and record["recorded_publication_acknowledged"] is True
    assert record["receipt"] == receipt and record["commands"] == []
    assert set(record["unavailable"]) == {"detailed_failure", "recovery_exposure"}
    assert record["result"]["registered_config_sha256"] == reader.TASK5_FRESH_R2_CONFIG_SHA256
    assert record["result"]["sha256"] == owned._identity(api.files[intake.RESULT])["sha256"]
    assert [path for _, path in api.downloads] == [producer.TERMINAL, producer.CLAIM,
        producer.OUTPUT + "/" + output.MANIFEST, result_path]
    assert all(revision != retained.BRANCH for revision, _ in api.path_reads)
    marker = tmp_path / "budget" / reader.BUDGET_MARKER
    assert marker.stat().st_mode & 0o777 == 0o600 and marker.parent.stat().st_mode & 0o777 == 0o700
    marker_bytes = marker.read_bytes()
    assert record["observation_sha256"] == owned._identity(marker_bytes)["sha256"]
    assert "budget_observation_verified" not in json.loads(marker_bytes)
    calls = deepcopy(api.calls)
    with pytest.raises(output.OutputPublicationRefused, match="^new_result_destination_required$"):
        read(api, "budget")
    assert api.calls == calls and marker.read_bytes() == marker_bytes
    with capsys.disabled():
        print("BOUNDARY four immutable bodies only: fixed controls then RESULT; budget projection and private no-clobber marker/readback verified")

    for index, mutation in enumerate((
        lambda api: api.terminal["authority"].update(provider_run_id="37101934437"),
        lambda api: api.terminal["authority"].update(provider_job_id=111147701026),
        lambda api: api.summary.update(source_sha="a" * 40),
        lambda api: api.summary.update(cell_id=reader.TASK5_KEEP_R2.expectation.cell_id),
        lambda api: api.terminal.update(request_sha256="b" * 64),
        lambda api: api.claim.update(expected_parent="76f51d0464b3c90d9ff80b78b656b9e7d45a0b6e"),
        lambda api: api.claim["predecessor"].update(exit_code=137),
        lambda api: api.summary.update(cleanup_confirmed=False),
        lambda api: api.terminal.update(publication_acknowledged=False),
    )):
        bad = make()
        mutation(bad)
        seal(bad)
        refuse(bad, "control-" + str(index), before_result=True)
    for index, key in enumerate(("terminal_identity", "claim_identity", "output_manifest_identity")):
        bad = make()
        bad.expected[key]["sha256"] = "0" * 64
        refuse(bad, "fixed-identity-" + str(index), before_result=True)
    bad = make()
    bad.expected["terminal_identity"]["size"] += 1
    refuse(bad, "fixed-size", before_result=True)
    for key in ("output_objects_sha256", "retained_authority_sha256"):
        bad = make()
        bad.expected[key] = "0" * 64
        refuse(bad, key, before_result=True)
    for revision, path in ((fixed["claim_commit"], producer.CLAIM), (fixed["output_commit"], result_path),
                           (fixed["terminal_commit"], producer.OUTPUT + "/" + intake.LEDGER)):
        bad = make()
        bad.writers[revision][path] = "f" * 40
        refuse(bad, "history-" + str(len(transports)), before_result=True)
    bad = make()
    bad.corrupt = result_path
    refuse(bad, "result-hash")
    assert bad.downloads[-1] == (fixed["output_commit"], result_path)

    for index, mutation in enumerate((
        lambda value: value.update(source="synthetic-wrong/source"),
        lambda value: value.update(run_id="wrong-config-run"),
        lambda value: value.update(condition="wrong-condition"),
        lambda value: value.update(publication_generation="wrong-generation"),
        lambda value: value.update(ordered_task_ids=[intake.registration.TASK4]),
        lambda value: value["results"][0].update(task_id=intake.registration.TASK4),
        lambda value: value.update(results=[]),
        lambda value: value["results"][0].update(observability=[]),
        lambda value: value["results"][0]["observability"].update(task_deadline=None),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(retention_bundle="keep"),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(task_id=intake.registration.TASK4),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(total_seconds=10801),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(attempt_seconds=1801),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(attempts_admitted=1.0),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(native_resumes=True),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(wait_seconds="12"),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(remaining_seconds=-1),
        lambda value: value["results"][0]["observability"]["task_deadline"].update(wait_seconds=None),
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
    bad.expected.update(terminal_identity=owned._identity(retained._encoded(bad.terminal)),
        output_manifest_identity=owned._identity(retained._encoded(bad.summary)),
        output_objects_sha256=owned._digest(bad.terminal["output_objects"]))
    refuse(bad, "fingerprint")

    for index in range(3):
        absent = make({})
        if index == 0:
            del absent.payload["results"][0]["observability"]
        elif index == 1:
            absent.payload["results"][0]["observability"] = {}
        seal(absent)
        result = read(absent, "absent-" + str(index))
        assert result["inference_budget_snapshot"] == {**dict.fromkeys(fields), "missing": dict.fromkeys(fields, "not_recorded")}
        assert result["status"] == "failed" and result["grade"] is None
    nullable = make({"total_seconds": 10800, "started_unix": None, "expires_unix": None, "remaining_seconds": None})
    snapshot = read(nullable, "nullable")["inference_budget_snapshot"]
    assert snapshot == {"total_seconds": 10800, **dict.fromkeys(fields[1:]), "missing": {
        "started_unix": "unavailable", "expires_unix": "unavailable", "remaining_seconds": "unavailable",
        "wait_seconds": "not_recorded", "attempts_admitted": "not_recorded", "native_resumes": "not_recorded"}}
    zeros = make({"total_seconds": 10800, **dict.fromkeys(fields[1:], 0)})
    assert read(zeros, "zeros")["inference_budget_snapshot"] == {"total_seconds": 10800, **dict.fromkeys(fields[1:], 0), "missing": {}}
    projector = reader._budget_projector()
    for invalid in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(output.OutputPublicationRefused, match="^grade_readout_budget_snapshot_refused$"):
            projector({"results": [{"observability": {"task_deadline": {"wait_seconds": invalid}}}]})
    with capsys.disabled():
        print("BOUNDARY source/task/config/hash/fingerprint/history refusals; missing, unavailable and recorded-zero snapshot semantics preserved")

    for index, readback in enumerate((False, True)):
        unresolved = make()
        writer = reader._write_no_clobber

        def lost_write(path, data, **kwargs):
            writer(path, data, **kwargs)
            if Path(path).name == reader.BUDGET_MARKER:
                raise OSError("SECRET-LIKE-ERROR lost marker acknowledgment")

        def lost_read(path, **kwargs):
            data = real_bytes(path, **kwargs)
            if Path(path).name == reader.BUDGET_MARKER:
                raise OSError("SECRET-LIKE-ERROR marker readback unavailable")
            return data

        with monkeypatch.context() as lost:
            lost.setattr(output if readback else reader, "_bytes" if readback else "_write_no_clobber",
                         lost_read if readback else lost_write)
            name = "unresolved-" + str(index)
            code, result = cli(unresolved, name)
            assert code == 2 and result["budget_observation_verified"] is False
            assert result["reason"] == "fresh_terminal_observation_unconfirmed"
        assert (tmp_path / name / reader.BUDGET_MARKER).is_file()
        calls = deepcopy(unresolved.calls)
        code, result = cli(unresolved, name)
        assert code == 2 and not result["budget_observation_verified"] and unresolved.calls == calls
    bad = make()
    bad.read_error = OSError("SECRET-LIKE-ERROR " + str(tmp_path))
    code, result = cli(bad, "private-error")
    assert code == 2 and result["reason"] == "fresh_budget_observation_refused"
    assert not (tmp_path / "private-error" / reader.BUDGET_MARKER).exists()

    old = make()
    with monkeypatch.context() as controls_only:
        controls_only.setattr(reader, "_budget_projector", forbidden)
        explicit = read(old, "controls-default", include_budget=False)
        other = make()
        arguments = options(other, "controls-omitted")
        del arguments["include_budget"]
        omitted = reader.observe_terminal(**arguments)
    assert explicit == omitted and explicit["outcome"] == "terminal_verified"
    assert "inference_budget_snapshot" not in explicit and explicit["unavailable"]["budget"]["reason"] == "not_recorded_in_terminal_controls"
    assert explicit["payload_bodies_verified"] is False and explicit["grading_input_ready"] is False
    assert len(old.downloads) == len(other.downloads) == 3
    stopped = make()
    stopped.summary.update(status="stopped", exit_code=None)
    seal(stopped)
    with monkeypatch.context() as controls_only:
        controls_only.setattr(reader, "_budget_projector", forbidden)
        result = read(stopped, "stopped-controls", include_budget=False)
    assert result["status"] == "stopped" and result["exit_code"] is None and result["grade"] is None
    assert result["payload_bodies_verified"] is False and len(stopped.downloads) == 3
    stopped.downloads.clear()
    refuse(stopped, "not-the-fixed-failed-outcome", before_result=True)
    failed_intake = make()
    with pytest.raises(output.OutputPublicationRefused, match="^fresh_result_success_required$"):
        reader.read_result(**{key: value for key, value in options(failed_intake, "not-success").items() if key != "include_budget"})
    assert all(name != result_path for _, name in failed_intake.downloads)

    # Current source checks stay separate from the historical grading ledger.
    assert reader.TASK5_FRESH_R2_BUDGET_CONTROLS == fixed
    for name, digest in observer.CURRENT_DEPENDENCIES.items():
        assert hashlib.sha256((ci.ROOT / "batch-runner" / name).read_bytes()).hexdigest() == digest
    assert observer.bridge.fixed_evidence_sha256() == "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d"
    assert observer.bridge.fixed_evidence_sha256("retention/keep-r2") == "25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0"
    assert observer.bridge._fixed("retention/keep-r2").RESULT["intake_sha256"] == "4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4"
    fixed_readers = (reader.FRESH_R1, reader.FRESH_R2, reader.KEEP_R2, reader.TASK5_FRESH_R1,
                     reader.TASK5_KEEP_R1, reader.TASK5_KEEP_R2, reader.TASK5_FRESH_R2)
    for profile in fixed_readers:
        checked, _, registered = reader._binding(profile.expectation, source["module_sha256"],
            fixed["terminal_commit"], False, binding=profile)
        assert registered["index"] == profile.ordinal
        assert {key: checked[key] for key in reader._frozen(profile)} == {key: pair[1] for key, pair in reader._frozen(profile).items()}
    assert reader.FRESH_R1.expectation is reader.EXPECTATION
    with capsys.disabled():
        print("BOUNDARY unresolved marker/readback stays unverified and non-replayable; controls-only/default and historical/current source separation preserved")

    # Pure workflow helpers were imported at collection, never under restored Popen.
    assert subprocess.Popen is not REAL_POPEN and subprocess.Popen.__name__ == "blocked"
    workflow_contract._assert_retention_execution_workflow_contract()
    workflow_contract._assert_retention_mode_routes()
    workflow = yaml.safe_load((ci.ROOT / ci.WORKFLOW).read_bytes())
    jobs = workflow["jobs"]
    steps = jobs[ci.PREPARE_JOB]["steps"]
    names = ("prepare", "execute", "observe_locator", "read_result", "observe_terminal", "observe_budget")
    cells = (ci.controller.FIRST_CELL_ID, *(profile.expectation.cell_id for profile in fixed_readers))
    assert len(workflow_contract._BUDGET_CELLS) == 8 and set(workflow_contract._BUDGET_CELLS) == set(cells)
    for selected, flags in itertools.product((*cells, "unknown"), itertools.product((False, True), repeat=6)):
        modes = dict(zip(names, flags))
        values = {"inputs." + key: value for key, value in modes.items()}
        values.update({"inputs.cell_id == '" + cell_id + "'": selected == cell_id for cell_id in cells})
        reading = modes["read_result"] and sum(flags) == 1
        terminal = modes["observe_terminal"] and sum(flags) == 1
        budget = modes["observe_budget"] and sum(flags) == 1
        for index in (9, 10, 11, 12, 13, 14):
            expected = ((reading and selected in cells[1:]) if index in (9, 10) else
                        ((reading or budget) and selected == cells[0]) if index in (11, 12) else
                        ((terminal or budget) and selected in cells[1:]))
            assert workflow_contract._boolean(steps[index]["if"], values) is expected
    preflight, step = steps[13:15]
    assert preflight["env"] == {"OBSERVE_BUDGET_ONLY": "${{ inputs.observe_budget }}"}
    assert preflight["run"] == steps[9]["run"] + (
        'if [[ "$OBSERVE_BUDGET_ONLY" == true ]]; then\n'
        "  printf '%s\\n' '" + reader.BUDGET_PROJECTOR_PIN[1] + "  batch-runner/codex_budget_pilot_grade_readout.py' | sha256sum --check --status\nfi\n")
    assert '"$(git rev-parse HEAD)" == "$REVIEWED_SOURCE_SHA"' in preflight["run"]
    assert "git status --porcelain=v1 --untracked-files=all" in preflight["run"]
    assert "secrets." not in preflight["run"]
    for index in (9, 13):
        pins = re.findall(r"'([0-9a-f]{64})  (batch-runner/[^']+)'", steps[index]["run"])
        expected = {"batch-runner/" + Path(path).name: digest for path, digest in reader._frozen(binding).values()}
        expected["batch-runner/" + Path(reader.__file__).name] = source["module_sha256"]
        if index == 13:
            expected["batch-runner/codex_budget_pilot_grade_readout.py"] = reader.BUDGET_PROJECTOR_PIN[1]
        assert len(pins) == len(expected) and {path: digest for digest, path in pins} == expected
        assert all(hashlib.sha256((ci.ROOT / path).read_bytes()).hexdigest() == digest for digest, path in pins)
    assert step["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}", "OBSERVE_BUDGET_ONLY": "${{ inputs.observe_budget }}"}
    assert step["timeout-minutes"] == 4 and jobs[ci.PREPARE_JOB]["timeout-minutes"] == 20
    assert "retention_terminal_args=(--observe-terminal --discover-terminal)" in step["run"]
    assert workflow_contract._budget_terminal_selection() in step["run"]
    command = shlex.split(next(line for line in step["run"].replace("\\\n", "").splitlines() if line.startswith("env -u ")))
    assert command[:17] == ["env", "-u", "GITHUB_TOKEN", "-u", "GH_TOKEN", "-u", "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "-u", "ACTIONS_ID_TOKEN_REQUEST_URL", "-u", "ACTIONS_RUNTIME_TOKEN", "timeout", "--signal=KILL", "180s",
        "python3", "batch-runner/codex_retention_fresh_r1_result_intake.py", "${retention_terminal_args[@]}"]
    assert command[command.index("--expected-reader-sha256") + 1] == source["module_sha256"]
    assert "stderr.log" not in step["run"].split("# Only the reviewed reader")[1]
    assert 'tee -a "$GITHUB_STEP_SUMMARY" < "$retention_terminal_parent/receipt.json"' in step["run"]
    assert not effects and all(not api.commits for api in transports)
    assert subprocess.Popen.__name__ == socket.create_connection.__name__ == "blocked"
    print(json.dumps({"scope": "synthetic_final_task5_result_only_budget_observation", "mode_cases": 576,
        "fixed_controls_before_result": True, "only_result_body_verified": True, "snapshot_missingness_preserved": True,
        "private_marker_readback_no_replay": True, "old_controls_only_preserved": True,
        "current_historical_pins_separate": True, "network_model_writer_child_paid_effects": len(effects)}, sort_keys=True))
