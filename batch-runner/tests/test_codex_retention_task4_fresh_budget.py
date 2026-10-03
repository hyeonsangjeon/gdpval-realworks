"""One combined offline proof for the two fixed failed Task4 FRESH budgets."""

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
# Import helper owners at collection, before process/network/model guards.
from .test_codex_retention_ci import REAL_POPEN
from . import test_codex_retention_ci_observation as workflow_contract
from . import test_codex_retention_fresh_r1_result_intake as fixtures
from .test_codex_retention_task5_fresh_r1_read import _task5_fixture, TASK5_FILE
from .test_codex_retention_task5_keep_r2_budget import _recorded_controls
from .test_codex_retention_task5_r1_budget import _assert_task5_r1_observations
from .test_codex_retention_result_intake import FILE, PRIVATE

ci, retained, output, owned, intake = reader.ci, reader.retained, reader.output, reader.owned, reader.intake


def _assert_task4_fresh_observations(readout):
    """Keep later supplied RESULT receipts separate from older controls-only evidence."""
    prior = deepcopy(readout)
    added = [prior["cells"][index].pop("current_budget_observation") for index in (1, 2)]
    canonical = (json.dumps(prior, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    assert hashlib.sha256(canonical).hexdigest() == "6b3830c740ffe6a540990c299887eb4f205e82eb42e71cce8b99e8c3e7feeffe"
    expected = (
        (reader.FRESH_R1, "37138725894", 111248535588, "2026-10-03T16:59:36.1876048Z",
         "d2b354bc9ad165fc18d90318dac3eb852e64f455f0fa31f89de3f2330f9c896c",
         "220b35dec4130fb5c83ffa3a1367f7acab41c9e3e3f740e228628df30de866c0",
         {"sha256": "b93c0d4b0d629ea8f351b60865eb7aa49c2a52e8634c73206d026aebd5112b5f", "size": 7771,
          "result_fingerprint": "bbbf5016111f61f15723a91f1ea792eee000e428c032efde88f37324f1cd0968",
          "recorded_prepared_fingerprint": "12055455235092daec59388f3f84bec93a602674eddac6ad064b7620201c426f",
          "registered_config_sha256": "5993b6d0c94ef1d56e808fab07941daed6e77d3f7adf7e055d9329043af63e02"},
         {"total_seconds": 10800, "started_unix": 1790850168.3271084, "expires_unix": 1790860968.3271084,
          "remaining_seconds": 0.0, "wait_seconds": 8983.719460487366,
          "attempts_admitted": 39, "native_resumes": 0, "missing": {}}),
        (reader.FRESH_R2, "37138900161", 111249054328, "2026-10-03T17:02:20.9246243Z",
         "7304dd060ec089542085d8156f295f20fd8e3bdfd9ead8af5766894a59c17c83",
         "dfee46e28de07e107384fb986bdc9c0d4d43e21fbefd200818a9004893a396a2",
         {"sha256": "c865b09977ca9a904c979531057f573ccc0c5358e20cfec90197853011afbf42", "size": 7737,
          "result_fingerprint": "6cf30c822000e29627ff28b70a8e6626c9f15e639515f295c4ef8008489a6124",
          "recorded_prepared_fingerprint": "2282906d3e47322497c96707a3931e892ef99309ebb89f7f97b888fea18da340",
          "registered_config_sha256": "7148453eb16dd8a0c6737bffe2fc5df42319dbb1a11afba2cdc2b90b649f305d"},
         {"total_seconds": 10800, "started_unix": 1790881801.5121758, "expires_unix": 1790892601.5121758,
          "remaining_seconds": 0.0, "wait_seconds": 8985.385900974274,
          "attempts_admitted": 39, "native_resumes": 0, "missing": {}}),
    )
    for actual, (profile, run, job, timestamp, digest, authority, result, snapshot) in zip(added, expected):
        row = readout["cells"][profile.ordinal]
        assert actual["source_addendum"] == (
            "Project5 leader order 2026-10-04 02:23 KST; actual RESULT-only receipt supplied by the leader, not a worker live read")
        assert actual["historical_scope"] == (
            "read_terminal_details_and_original_limits_preserved_as_terminal_only_evidence_not_backfilled")
        assert (actual["mode"], actual["source_sha"], actual["run_id"], actual["job_id"], actual["receipt_utc"]) == (
            "observe_budget", "c4828cc83892fb9f844599bb6c3be3d66500d9e8", run, job, timestamp)
        assert actual["outcome"] == "budget_observation_verified" and actual["approval_execution_skipped"] is True
        assert actual["marker_sha256"] == digest
        assert actual["historical_reader_sha256"] == "9359eab1be22b54bc6f18092560308058a820dde0a55c365a9ee263f6f9c0f09"
        assert actual["budget_projector_sha256"] == "96d0dd63f5d67aa9f54e95615b4467357aa65ea5223418be47e120cc3ad5e815"
        assert actual["result"] == result
        assert owned._canonical_json(actual["inference_budget_snapshot"]) == owned._canonical_json(snapshot)
        assert actual["terminal_commit"] == row["terminal"]["revision"]
        assert actual["output_commit"] == row["output_manifest"]["revision"]
        assert actual["retained_authority_sha256"] == authority
        assert actual["retained_authority_provenance"] == (
            "newly_derived_for_this_observation_not_backfilled_into_digest_absent_historical_read")
        assert "retained_authority_sha256" not in row["read"]
        fixed = reader.FRESH_R1_BUDGET_CONTROLS if profile is reader.FRESH_R1 else reader.FRESH_R2_BUDGET_CONTROLS
        assert "retained_authority_sha256" not in fixed
        assert actual["supplied_request_binding"] == reader._request_context(profile)
        assert actual["result_body_verified"] is True and actual["payload_verification_scope"] == "inference_result_only"
        for key in ("payload_bodies_verified", "ledger_body_verified", "deliverable_bodies_verified", "grading_input_ready",
                    "fresh_origin_authentication", "prepared_input_independently_verified", "git_parent_cas_independently_verified",
                    "live_read_repeated_here", "replay_authorized"):
            assert actual[key] is False
        assert (actual["status"], actual["exit_code"], actual["cleanup_confirmed"], actual["grade"]) == ("failed", 1, True, None)
        assert actual["writer_acknowledgment"] == "not_established" and actual["recorded_publication_acknowledged"] is True
        assert actual["measurement_limits"] == readout["cells"][7]["current_budget_observation"]["measurement_limits"]
        assert actual["unavailable"] == readout["cells"][7]["current_budget_observation"]["unavailable"]
        assert row["terminal_details"]["budget"] is None and row["read"]["payload_bodies_verified"] is False
    assert all("current_budget_observation" not in readout["cells"][index] for index in (0, 3))


def test_task4_fresh_budgets_are_fixed_private_and_model_free(tmp_path, monkeypatch, capsys):
    effects, transports, failures = [], [], []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("Task4 budget proof crossed a network, model, remote writer, child or paid boundary")

    producers = (fresh_r1, fresh_r2, keep_r2, task5_fresh_r1, task5_keep_r1, task5_keep_r2, task5_fresh_r2)
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
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    assert subprocess.Popen is not REAL_POPEN and subprocess.Popen.__name__ == "blocked"
    assert socket.create_connection.__name__ == socket.socket.connect.__name__ == "blocked"

    # If CLI redaction hides an unexpected failure, retain classes/relative
    # frames for its first boundary, never private exception text or payloads.
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
    profiles = (
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
        if profile is reader.FRESH_R1 or profile is reader.FRESH_R2:
            assert "retained_authority_sha256" not in row["read"]
            assert fixed == {
                "terminal_commit": row["terminal"]["revision"],
                "terminal_identity": {"sha256": row["terminal"]["sha256"], "size": row["terminal"]["bytes"]},
                "claim_commit": row["claim"]["revision"],
                "claim_identity": {"sha256": row["claim"]["sha256"], "size": row["claim"]["bytes"]},
                "output_commit": row["output_manifest"]["revision"],
                "output_manifest_identity": {"sha256": row["output_manifest"]["sha256"], "size": row["output_manifest"]["bytes"]},
                "output_objects_sha256": row["output_objects_sha256"],
                "status": "failed", "exit_code": 1, "cleanup_confirmed": True}
            successor = fresh_r2 if profile is reader.FRESH_R1 else keep_r2
            assert fixed == {key: successor.PREDECESSOR[key] for key in fixed}
        else:
            assert fixed == _recorded_controls(row)
        assert profile.expectation == ci.TerminalExpectation(
            row["producer"]["request_sha256"], row["producer"]["source_sha"], row["cell_id"])
        assert (profile.run_id, profile.execution_job_id, row["producer"]["attempt"]) == (
            row["producer"]["run_id"], row["producer"]["execution_job_id"], 1)
        assert (profile.retention_bundle, profile.repetition) == (row["retention_bundle"], row["repetition"])
        assert producer.PREDECESSOR["terminal_commit"] == row["preceding_registered_inference_terminal"]
        cell = intake.controller._adapted_cell(plan["cells"][profile.ordinal])
        assert cell["config_sha256"] == intake.registration.seal(cell["config"]) == config_hash
    assert reader.FRESH_R1_CONFIG_SHA256 == profiles[0][-1] and reader.FRESH_R2_CONFIG_SHA256 == profiles[1][-1]
    assert reader.TASK5_KEEP_R1.materialized_grader_source_sha256 is None
    _assert_task4_fresh_observations(readout)
    _assert_task5_r1_observations(readout)
    assert hashlib.sha256((ci.ROOT / "tasks/codex_budget_pilot/REPORT.md").read_bytes()).hexdigest() == (
        "88a37d8cfdae6c3c05a79db78827bfe2d59fdcd944067e4f6fcd7f387dddae0e")
    report = (ci.ROOT / "tasks/codex_budget_pilot/RETENTION_DIAGNOSTIC_REPORT.md").read_text()
    assert "Both successful Task4 KEEP budgets remain unobserved" in " ".join(report.split())
    for index in (4, 5):
        actual = readout["cells"][index]["current_budget_observation"]
        for value in actual["inference_budget_snapshot"].values():
            if type(value) in (int, float):
                assert str(value) in report
        assert actual["marker_sha256"] in report and actual["result"]["sha256"] in report
    with capsys.disabled():
        print("BOUNDARY six fixed configurations/controls; two actual Task5 r1 additions preserve all delivered JSON fields and pilot bytes")

    source = reader.reader_identity(binding=reader.TASK5_FRESH_R2)
    monkeypatch.setattr(intake.registration, "compile_plan", lambda: deepcopy(plan))
    receipt = ci.project_cost_receipt(CostReceipt(status="partial", model_calls=1,
        known_cost_usd=Decimal("0.01"), model_cost_usd=Decimal("0.01"),
        usage={"input_tokens": 12, "cached_input_tokens": 8, "output_tokens": 3, "reasoning_tokens": 2},
        missing_reasons=("synthetic_missing_cost",)).as_dict())
    fields = ("total_seconds", "started_unix", "expires_unix", "remaining_seconds",
              "wait_seconds", "attempts_admitted", "native_resumes")
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
            "remaining_seconds": 100.0, "wait_seconds": 12.5, "attempts_admitted": 2, "native_resumes": 0}

    default_snapshot = object()

    def make(profile, snapshot=default_snapshot):
        spec = next(spec for spec in profiles if spec[0] is profile)
        fixed = controls[spec[2]]
        revisions(fixed)
        # Each source role stays with its established exclusive fixture owner.
        # Task4 uses its original transport, never the Task5 task-ID rewriter.
        task4 = profile is reader.FRESH_R1 or profile is reader.FRESH_R2
        factory = fixtures.FreshResultHF if task4 else _task5_fixture
        api = factory(plan, binding=profile, receipt=receipt, with_ledger=True, terminal_head=fixed["terminal_commit"])
        transports.append(api)
        api.fixed, api.profile, api.spec = fixed, profile, spec
        api.files.pop(FILE if task4 else TASK5_FILE)
        # Ordinary FRESH/r1 success historically accepts another positive job;
        # its terminal/budget mode requires the exact supplied execution job.
        api.claim["authority"]["provider_job_id"] = profile.execution_job_id
        api.terminal["authority"] = deepcopy(api.claim["authority"])
        api.payload["condition"] = plan["cells"][profile.ordinal]["config"]["condition_a"]["name"]
        api.payload["results"][0].update(status="error", deliverable_files=[], deliverable_file_records=[],
            observability={"task_deadline": deepcopy(complete(profile) if snapshot is default_snapshot else snapshot)})
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
            (str(tmp_path), api.repo, TOKEN, PRIVATE.decode().strip(), FILE, TASK5_FILE, "SECRET-LIKE-ERROR"))
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

    for profile, producer, *_ in profiles[:2]:
        prefix, api = "task4-fresh-r" + str(profile.repetition) + "-", make(profile)
        with monkeypatch.context() as early:
            early.setattr(retained, "_session", forbidden)
            early.setattr(reader, "_budget_projector", forbidden)
            assert reader.main([], _test_api=api) == 0 and captured(api)["cell_id"] == reader.FRESH_R1.expectation.cell_id
            for other_mode in ("--read", "--observe-terminal"):
                assert reader.main(["--observe-budget", other_mode], _test_api=api) == 2
                assert captured(api)["reason"] == "invalid_arguments"
            wrong_profiles = (reader.KEEP_R2, *(spec[0] for spec in profiles if spec[0] is not profile),
                replace(profile), replace(profile, run_id="1"), replace(profile, execution_job_id=1), object())
            for index, changes in enumerate((
                *({"binding": other} for other in wrong_profiles),
                {"include_budget": 1}, {"expected_reader_sha256": "c" * 64},
                {"expectation": intake.EXPECTATION},  # Successful Task4 KEEP/r1 is not budget eligible.
                {"expectation": replace(profile.expectation, cell_id="unknown")},
                {"expectation": replace(profile.expectation, source_sha="a" * 40)},
                {"expectation": replace(profile.expectation, request_sha256="b" * 64)},
                {"terminal_revision": producer.PREDECESSOR["terminal_commit"]},
                {"terminal_revision": None, "discover_terminal": True},
            )):
                name = prefix + "early-" + str(index)
                refuse(api, name, before_result=True, **changes)
                assert not (tmp_path / name).exists()
            for index, mutation in enumerate((
                lambda value: value["cells"][profile.ordinal].update(config_sha256=reader.TASK5_FRESH_R2_CONFIG_SHA256),
                lambda value: value["cells"][profile.ordinal]["config"]["execution"].update(timeout=1801),
            )):
                wrong = deepcopy(plan)
                mutation(wrong)
                early.setattr(intake.registration, "compile_plan", lambda: wrong)
                refuse(api, prefix + "sealed-config-" + str(index), before_result=True)
        real_bytes, real_import = output._bytes, builtins.__import__
        for bad_path in (Path(reader.__file__), *(Path(path) for path, _ in reader._frozen(profile).values()),
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
                               else producer.__name__)
                    if name == guarded:
                        return forbidden()
                    return real_import(name, *args, **kwargs)

                with monkeypatch.context() as corrupt:
                    corrupt.setattr(output, "_bytes", changed)
                    corrupt.setattr(builtins, "__import__", no_import)
                    corrupt.setattr(retained, "_session", forbidden)
                    name = prefix + "pin-" + bad_path.stem + str(missing)
                    refuse(api, name, before_result=True)
                    assert not (tmp_path / name).exists()
        assert not api.calls and not effects
    with capsys.disabled():
        print("BOUNDARY both Task4 FRESH identities/configs; KEEP/unknown/copied bindings and changed/missing pins refused before session")

    monkeypatch.setenv("HF_TOKEN", TOKEN)  # Authored fixture token, never a credential.
    for profile, producer, _, expected_format, marker_name, config_hash in profiles[:2]:
        prefix, api = "task4-fresh-r" + str(profile.repetition) + "-", make(profile)
        code, record = cli(api, prefix + "budget")
        assert code == 0, {"boundary": prefix + "first_result_budget_projection", "original_causes": failures[-1:]}
        assert record["format"] == expected_format and record["mode"] == "observe_budget"
        assert record["budget_observation_verified"] is True
        assert record["inference_budget_snapshot"] == {**{key: complete(profile)[key] for key in fields}, "missing": {}}
        assert record["inference_budget_snapshot"]["attempts_admitted"] != record["receipt"]["model_calls"]
        assert record["result"] == {**owned._identity(api.files[intake.RESULT]),
            "result_fingerprint": api.payload["result_fingerprint"],
            "recorded_prepared_fingerprint": api.payload["prepared_fingerprint"],
            "registered_config_sha256": config_hash}
        assert not {"results", "raw_payload", "stderr", "error", "deliverable_files"} & record.keys()
        assert record["supplied_request_binding"] == reader._request_context(profile)
        assert record["predecessor"] == producer.PREDECESSOR
        assert record["expected_execution_job_id"] == record["recorded_provider_job_id"] == profile.execution_job_id
        assert (record["status"], record["exit_code"], record["cleanup_confirmed"], record["grade"]) == ("failed", 1, True, None)
        assert record["result_body_verified"] and record["payload_verification_scope"] == "inference_result_only"
        for key in ("payload_bodies_verified", "ledger_body_verified", "deliverable_bodies_verified", "grading_input_ready",
                    "fresh_origin_authentication", "prepared_input_independently_verified", "git_parent_cas_independently_verified",
                    "launch_authorized", "grading_launched", "admission_attempted", "replay_authorized", "invoice_complete"):
            assert record[key] is False
        assert record["writer_acknowledgment"] == "not_established" and record["recorded_publication_acknowledged"] is True
        assert record["retained_authority_sha256"] == owned._digest(api.terminal["authority"])
        assert record["receipt"] == receipt and record["commands"] == []
        assert set(record["unavailable"]) == {"detailed_failure", "recovery_exposure"}
        result_path = producer.OUTPUT + "/" + intake.RESULT
        assert api.downloads == [(api.fixed["terminal_commit"], producer.TERMINAL), (api.fixed["claim_commit"], producer.CLAIM),
            (api.fixed["output_commit"], producer.OUTPUT + "/" + output.MANIFEST), (api.fixed["output_commit"], result_path)]
        assert all(revision != retained.BRANCH for revision, _ in api.path_reads)
        marker = tmp_path / (prefix + "budget") / marker_name
        marker_bytes, calls = marker.read_bytes(), deepcopy(api.calls)
        assert marker.stat().st_mode & 0o777 == 0o600 and marker.parent.stat().st_mode & 0o777 == 0o700
        assert record["observation_sha256"] == owned._identity(marker_bytes)["sha256"]
        assert all(not (marker.parent / other[4]).exists() for other in profiles if other[0] is not profile)
        with pytest.raises(output.OutputPublicationRefused, match="^new_result_destination_required$"):
            read(api, prefix + "budget")
        assert api.calls == calls and marker.read_bytes() == marker_bytes

        for index, mutation in enumerate((
            lambda api: api.terminal["authority"].update(provider_run_id=reader.TASK5_FRESH_R2.run_id),
            lambda api: api.terminal["authority"].update(provider_job_id=reader.TASK5_FRESH_R2.execution_job_id),
            lambda api: api.summary.update(source_sha=reader.TASK5_FRESH_R2.expectation.source_sha),
            lambda api: api.summary.update(cell_id=reader.TASK5_FRESH_R2.expectation.cell_id),
            lambda api: api.terminal.update(request_sha256=reader.TASK5_FRESH_R2.expectation.request_sha256),
            lambda api: api.claim.update(expected_parent=api.fixed["terminal_commit"]),
            lambda api: api.claim["predecessor"].update(cell_id="wrong-predecessor"),
            lambda api: api.summary.update(cleanup_confirmed=False),
            lambda api: api.terminal.update(publication_acknowledged=False),
        )):
            bad = make(profile)
            mutation(bad)
            seal(bad)
            refuse(bad, prefix + "control-" + str(index), before_result=True)
        for key in ("terminal_identity", "claim_identity", "output_manifest_identity"):
            for field in ("sha256", "size"):
                bad = make(profile)
                bad.expected[key][field] = "0" * 64 if field == "sha256" else bad.expected[key][field] + 1
                refuse(bad, prefix + key + field, before_result=True)
        bad = make(profile)
        bad.expected["output_objects_sha256"] = "0" * 64
        refuse(bad, prefix + "object-set", before_result=True)
        # With no separately supplied Task4 authority digest, the pinned
        # terminal still rejects a well-formed but changed embedded authority.
        bad = make(profile)
        pinned_terminal = deepcopy(bad.expected["terminal_identity"])
        bad.claim["authority"]["runner_id"] += 1
        bad.terminal["authority"] = deepcopy(bad.claim["authority"])
        seal(bad)
        bad.expected["terminal_identity"] = pinned_terminal
        refuse(bad, prefix + "authority-inside-terminal", before_result=True)
        for index, (revision, path) in enumerate((
            (api.fixed["claim_commit"], producer.CLAIM), (api.fixed["output_commit"], result_path),
            (api.fixed["terminal_commit"], producer.OUTPUT + "/" + intake.LEDGER),
        )):
            bad = make(profile)
            bad.writers[revision][path] = "f" * 40
            refuse(bad, prefix + "history-" + str(index), before_result=True)
        bad = make(profile)
        bad.corrupt = result_path
        refuse(bad, prefix + "result-hash-size")
        assert bad.downloads[-1] == (bad.fixed["output_commit"], result_path)
        for index, mutation in enumerate((
            lambda value: value.update(source="synthetic-wrong/source"),
            lambda value: value.update(run_id="wrong-config-run"),
            lambda value: value.update(condition="wrong-condition"),
            lambda value: value.update(ordered_task_ids=[intake.registration.TASK5]),
            lambda value: value["results"][0].update(task_id=intake.registration.TASK5),
            lambda value: value["results"][0].update(observability=[]),
            lambda value: value["results"][0]["observability"].update(task_deadline=None),
            lambda value: value["results"][0]["observability"]["task_deadline"].update(retention_bundle="keep"),
            lambda value: value["results"][0]["observability"]["task_deadline"].update(repetition=3 - profile.repetition),
            lambda value: value["results"][0]["observability"]["task_deadline"].update(total_seconds=10801),
            lambda value: value["results"][0]["observability"]["task_deadline"].update(attempt_seconds=1801),
            lambda value: value["results"][0]["observability"]["task_deadline"].update(attempts_admitted=1.0),
            lambda value: value["results"][0]["observability"]["task_deadline"].update(native_resumes=True),
            lambda value: value["results"][0]["observability"]["task_deadline"].update(wait_seconds="12"),
            lambda value: value["results"][0]["observability"]["task_deadline"].update(remaining_seconds=-1),
            lambda value: value["cost_ledger"].update(sha256="0" * 64),
        )):
            bad = make(profile)
            mutation(bad.payload)
            seal(bad)
            refuse(bad, prefix + "payload-" + str(index))
            assert bad.downloads[-1] == (bad.fixed["output_commit"], result_path)
        bad = make(profile)
        bad.payload["result_fingerprint"] = "0" * 64
        bad.files[intake.RESULT] = (json.dumps(bad.payload, sort_keys=True) + "\n").encode()
        bad.seed()
        pin_controls(bad)
        refuse(bad, prefix + "fingerprint")
        absent = make(profile, {})
        del absent.payload["results"][0]["observability"]
        seal(absent)
        assert read(absent, prefix + "absent")["inference_budget_snapshot"] == {
            **dict.fromkeys(fields), "missing": dict.fromkeys(fields, "not_recorded")}
        nullable = make(profile, {"total_seconds": 10800, "remaining_seconds": None})
        assert read(nullable, prefix + "nullable")["inference_budget_snapshot"] == {
            "total_seconds": 10800, **dict.fromkeys(fields[1:]), "missing": {
                **dict.fromkeys(fields[1:], "not_recorded"), "remaining_seconds": "unavailable"}}
        zeros = make(profile, {"total_seconds": 10800, **dict.fromkeys(fields[1:], 0)})
        assert read(zeros, prefix + "zeros")["inference_budget_snapshot"] == {
            "total_seconds": 10800, **dict.fromkeys(fields[1:], 0), "missing": {}}
        with capsys.disabled():
            print("BOUNDARY " + prefix + "controls/history before RESULT; exact authority/job, tamper and missing/null/zero checks")

        writer, real_bytes = reader._write_no_clobber, output._bytes
        for failure in ("write", "readback"):
            unresolved, name = make(profile), prefix + "lost-" + failure

            def lost_write(path, data, **kwargs):
                writer(path, data, **kwargs)
                if Path(path).name == marker_name:
                    raise OSError("SECRET-LIKE-ERROR lost marker acknowledgment")

            def lost_readback(path, **kwargs):
                if Path(path).name == marker_name:
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
            assert (tmp_path / name / marker_name).is_file()
            calls = deepcopy(unresolved.calls)
            code, result = cli(unresolved, name)
            assert code == 2 and not result["budget_observation_verified"] and unresolved.calls == calls
        bad = make(profile)
        bad.read_error = OSError("SECRET-LIKE-ERROR " + str(tmp_path))
        code, result = cli(bad, prefix + "private-error")
        assert code == 2 and result["reason"] == "fresh_budget_observation_refused"
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
            reader.read_result(**{key: value for key, value in options(failed_intake, prefix + "not-success").items()
                                  if key != "include_budget"})
        assert all(path != result_path for _, path in failed_intake.downloads)

    # Directly coupled synthetic Task5 compatibility, not any earlier test or
    # consumed real observation. Their fixed controls and marker formats stay.
    for profile, _, _, expected_format, marker_name, config_hash in profiles[2:]:
        prefix, api = "task5-" + profile.retention_bundle + "-r" + str(profile.repetition) + "-", make(profile)
        record = read(api, prefix + "budget")
        assert record["format"] == expected_format and record["result"]["registered_config_sha256"] == config_hash
        assert record["inference_budget_snapshot"] == {**{key: complete(profile)[key] for key in fields}, "missing": {}}
        assert (tmp_path / (prefix + "budget") / marker_name).is_file()
        assert record["supplied_request_binding"] == reader._request_context(profile)
        control = make(profile)
        with monkeypatch.context() as controls_only:
            controls_only.setattr(reader, "_budget_projector", forbidden)
            record = read(control, prefix + "controls", include_budget=False)
        assert len(control.downloads) == 3 and record["payload_bodies_verified"] is False
        assert "inference_budget_snapshot" not in record
    assert all(getattr(reader, name) == fixed for name, fixed in controls.items())
    for name, digest in observer.CURRENT_DEPENDENCIES.items():
        assert hashlib.sha256((ci.ROOT / "batch-runner" / name).read_bytes()).hexdigest() == digest
    assert observer.bridge.fixed_evidence_sha256() == "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d"
    assert observer.bridge.fixed_evidence_sha256("retention/keep-r2") == "25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0"
    assert observer.bridge._fixed("retention/keep-r2").RESULT["intake_sha256"] == "4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4"
    with capsys.disabled():
        print("BOUNDARY Task4 private no-clobber/lost-ack/no-replay; Task5/control-only compatibility and historical grade evidence unchanged")

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
        print(json.dumps({"scope": "synthetic_combined_task4_fresh_result_only_budget_observation", "new_profiles": 2,
            "closed_budget_profiles": 8, "mode_cases": mode_cases, "fixed_controls_before_result": True,
            "authority_bound_by_exact_terminal_bytes": True, "sealed_task4_configs": True,
            "missing_null_zero_preserved": True, "private_marker_readback_no_replay": True,
            "unchanged_task5_controls_only_paid_isolation": True, "current_historical_pins_separate": True,
            "actual_task5_r1_receipts_separate_from_synthetic_proof": True,
            "prior_json_fields_r2_receipts_original_pilot_unchanged": True,
            "successful_task4_keep_budgets_unobserved": True, "network_model_writer_child_paid_effects": len(effects)}, sort_keys=True))
