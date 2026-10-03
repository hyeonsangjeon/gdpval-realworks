"""One combined offline proof for the two fixed Task5 r1 budget profiles."""

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
import codex_retention_task5_fresh_r1 as fresh_r1
import codex_retention_task5_keep_r1 as keep_r1
import codex_retention_task5_keep_r2 as keep_r2
import codex_retention_task5_fresh_r2 as fresh_r2
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from core.cost_receipts import CostReceipt
from .test_codex_budget_pilot_retention import TOKEN, offline  # noqa: F401
# Collection-time imports preserve the existing process/network fixture guards.
from .test_codex_retention_ci import REAL_POPEN
from . import test_codex_retention_ci_observation as workflow_contract
from . import test_codex_retention_fresh_r1_result_intake as fixtures
from .test_codex_retention_task5_fresh_r1_read import _task5_fixture, TASK5_FILE
from .test_codex_retention_task5_keep_r2_budget import _recorded_controls
from .test_codex_retention_result_intake import PRIVATE

ci, retained, output, owned, intake = reader.ci, reader.retained, reader.output, reader.owned, reader.intake


def _assert_task5_r1_observations(readout):
    """Check the supplied additions without treating synthetic reads as evidence."""
    prior = deepcopy(readout)
    # The later Task4 FRESH observations are not part of this historical snapshot.
    for index in (1, 2):
        prior["cells"][index].pop("current_budget_observation")
    added = [prior["cells"][index].pop("current_budget_observation") for index in (4, 5)]
    canonical = (json.dumps(prior, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    assert hashlib.sha256(canonical).hexdigest() == "eaefa00b1a8db81b9a12dd914135c0fbf2c279d09697b4cb1cb499e983d369de"
    expected = (
        (reader.TASK5_FRESH_R1, "37131238762", 111226607598, "2026-10-03T14:55:40.4040030Z",
         "883f64c6f1c8190c9fde011ba11d33b436438b6ea9c62577d6099f41a398d5c3",
         {"sha256": "eda9982c2812a5d4e1519c952f65438d1395b5526d07515fcf066dc604a1579a", "size": 7635,
          "result_fingerprint": "591f1f7f8e1a55aa82b7fcf759d3fe8edf51e5ccf199b7e082294605165fb79a",
          "recorded_prepared_fingerprint": "73ddcf56510ac10a676d58b6b49c5aef61efbce56f1a03795f006748bc84e575",
          "registered_config_sha256": "d67cbfeb3a26716d445b36a4466d5dc55559652381db71056aaf44a50a43e2eb"},
         {"total_seconds": 10800, "started_unix": 1790959571.661407, "expires_unix": 1790970371.661407,
          "remaining_seconds": 4909.906562328339, "wait_seconds": 3781.06050658226,
          "attempts_admitted": 18, "native_resumes": 0, "missing": {}}),
        (reader.TASK5_KEEP_R1, "37131339406", 111227047774, "2026-10-03T14:58:10.8491476Z",
         "a55103477c3be7571e736546b76d338dda6cd12ba908b569af65aef3b7e9febc",
         {"sha256": "137dec5dc2c4c2c0614ba253732bc6ebc0388ac9d1d511908f0d618ed7c09a54", "size": 7593,
          "result_fingerprint": "689cd06e107143d05f35f514d6575fb0978d7f044ebaaf9c92f5e7b47015280a",
          "recorded_prepared_fingerprint": "fec4fe641e3ef97ebb88a8c92a3663b884c550b756455f05d8d9feeaef8d9625",
          "registered_config_sha256": "4c75e2f0d8eb5a197fc44c2dc71b1abc166334c350791224ab5e3abc1a017cc3"},
         {"total_seconds": 10800, "started_unix": 1790976592.4457858, "expires_unix": 1790987392.4457858,
          "remaining_seconds": 7373.157982349396, "wait_seconds": 2580.858815908432,
          "attempts_admitted": 13, "native_resumes": 12, "missing": {}}),
    )
    for actual, (profile, run, job, timestamp, digest, result, snapshot) in zip(added, expected):
        row = readout["cells"][profile.ordinal]
        assert actual["source_addendum"] == (
            "Project5 leader order 2026-10-04 00:19 KST; actual RESULT-only receipt supplied by the leader, not a worker live read")
        assert (actual["mode"], actual["source_sha"], actual["run_id"], actual["job_id"], actual["receipt_utc"]) == (
            "observe_budget", "3d43a674e47d700dd874680c053a91bc1807b693", run, job, timestamp)
        assert actual["outcome"] == "budget_observation_verified" and actual["approval_execution_skipped"] is True
        assert actual["marker_sha256"] == digest
        assert actual["historical_reader_sha256"] == "dd23824360e03f415feb5c7d247024ac7d67300c4ed7f2120e0eb2c9d6e47eb9"
        assert actual["budget_projector_sha256"] == "96d0dd63f5d67aa9f54e95615b4467357aa65ea5223418be47e120cc3ad5e815"
        assert actual["result"] == result
        assert owned._canonical_json(actual["inference_budget_snapshot"]) == owned._canonical_json(snapshot)
        assert actual["terminal_commit"] == row["terminal"]["revision"]
        assert actual["output_commit"] == row["output_manifest"]["revision"]
        assert actual["retained_authority_sha256"] == row["read"]["retained_authority_sha256"]
        assert actual["supplied_request_binding"] == reader._request_context(profile)
        assert (actual["status"], actual["exit_code"], actual["cleanup_confirmed"], actual["grade"]) == ("failed", 1, True, None)
        assert actual["result_body_verified"] is True and actual["payload_verification_scope"] == "inference_result_only"
        assert actual["writer_acknowledgment"] == "not_established" and actual["recorded_publication_acknowledged"] is True
        for key in ("payload_bodies_verified", "ledger_body_verified", "deliverable_bodies_verified", "grading_input_ready",
                    "fresh_origin_authentication", "prepared_input_independently_verified", "git_parent_cas_independently_verified",
                    "live_read_repeated_here", "replay_authorized"):
            assert actual[key] is False
        assert actual["historical_scope"] == "read_terminal_details_and_original_limits_preserved_as_terminal_only_evidence_not_backfilled"
        assert actual["measurement_limits"] == readout["cells"][7]["current_budget_observation"]["measurement_limits"]
        assert actual["unavailable"] == readout["cells"][7]["current_budget_observation"]["unavailable"]
        assert row["terminal_details"]["budget"] is None and row["read"]["payload_bodies_verified"] is False
    assert added[1]["supplied_request_binding"]["materialized_grader_source_sha256"] is None
    assert all("current_budget_observation" not in readout["cells"][index] for index in (0, 3))


def test_task5_r1_budgets_are_fixed_private_and_model_free(tmp_path, monkeypatch, capsys):
    effects, transports, failures = [], [], []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("r1 budget proof crossed a network, model, remote writer, child or paid boundary")

    for owner, names in (
        (ci, ("execute", "verify_approval", "verify_job_origin", "verify_terminal")),
        *((producer, ("execute", "_predecessor", "verify_terminal"))
          for producer in (fresh_r1, keep_r1, keep_r2, fresh_r2)),
        *((admission, ("__init__",)) for admission in (
            fresh_r1._Task5FreshR1Admission, keep_r1._Task5KeepR1Admission,
            keep_r2._Task5KeepR2Admission, fresh_r2._Task5FreshR2Admission, ci._Admission)),
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

    # Keep original exception classes and relative frames if CLI redaction
    # hides an unexpected assertion; never disclose private exception strings.
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
        (reader.TASK5_FRESH_R1, fresh_r1, "TASK5_FRESH_R1_BUDGET_CONTROLS",
         "retention-task5-fresh-r1-budget-observation-v1", "retention-task5-fresh-r1-budget-observation.json",
         "d67cbfeb3a26716d445b36a4466d5dc55559652381db71056aaf44a50a43e2eb"),
        (reader.TASK5_KEEP_R1, keep_r1, "TASK5_KEEP_R1_BUDGET_CONTROLS",
         "retention-task5-keep-r1-budget-observation-v1", "retention-task5-keep-r1-budget-observation.json",
         "4c75e2f0d8eb5a197fc44c2dc71b1abc166334c350791224ab5e3abc1a017cc3"),
        (reader.TASK5_KEEP_R2, keep_r2, "TASK5_KEEP_R2_BUDGET_CONTROLS",
         "retention-task5-keep-r2-budget-observation-v1", "retention-task5-keep-r2-budget-observation.json",
         "1bda6431161ff4d27e751b3475979f861eb875beb7d16a608c7649830f051286"),
        (reader.TASK5_FRESH_R2, fresh_r2, "TASK5_FRESH_R2_BUDGET_CONTROLS",
         "retention-task5-fresh-r2-budget-observation-v1", "retention-task5-fresh-r2-budget-observation.json",
         "3dd0af0802619dd60cc9eda5c492f6b75cd641463dca84a68ad5ad362e56074a"),
    )
    controls = {name: deepcopy(getattr(reader, name)) for _, _, name, *_ in profiles}
    readout = json.loads((ci.ROOT / "tasks/codex_budget_pilot/retention_diagnostic_readout.json").read_bytes())
    plan = intake.registration.compile_plan()
    for profile, producer, name, _, _, config_hash in profiles:
        row = readout["cells"][profile.ordinal]
        assert controls[name] == _recorded_controls(row)
        assert profile.expectation == ci.TerminalExpectation(
            row["producer"]["request_sha256"], row["producer"]["source_sha"], row["cell_id"])
        assert (profile.run_id, profile.execution_job_id, row["producer"]["attempt"]) == (
            row["producer"]["run_id"], row["producer"]["execution_job_id"], 1)
        assert (profile.retention_bundle, profile.repetition) == (row["retention_bundle"], row["repetition"])
        assert producer.PREDECESSOR["terminal_commit"] == row["preceding_registered_inference_terminal"]
        cell = intake.controller._adapted_cell(plan["cells"][profile.ordinal])
        assert cell["config_sha256"] == intake.registration.seal(cell["config"]) == config_hash
    assert reader.TASK5_FRESH_R1_CONFIG_SHA256 == profiles[0][-1]
    assert reader.TASK5_KEEP_R1_CONFIG_SHA256 == profiles[1][-1]
    assert reader.TASK5_KEEP_R1.materialized_grader_source_sha256 is None
    assert readout["cells"][5]["supplied_materialized_grader_source_sha256"] == (
        "75f38c05e5c348e481e54f4c0b2000772c2414d7bae7519b1f2a38d92e1e0dc5")
    _assert_task5_r1_observations(readout)

    # Only the newly supplied KEEP receipt may differ from the delivered JSON.
    # This is evidence preservation inside the new selector, not a report rerun.
    prior = deepcopy(readout)
    # Exclude the later Task4 FRESH and Task5 r1 observations from this older snapshot.
    for index in (1, 2, 4, 5):
        prior["cells"][index].pop("current_budget_observation")
    actual = prior["cells"][6].pop("current_budget_observation")
    canonical = (json.dumps(prior, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    # Python canonicalization retains the delivered 0.0 spelling (unlike jq).
    assert hashlib.sha256(canonical).hexdigest() == "bb8749e42de933000f126299616bdc2235c63bf420f6a4ebf5a7c16512924965"
    assert (actual["mode"], actual["run_id"], actual["job_id"], actual["receipt_utc"]) == (
        "observe_budget", "37125749122", 111210580807, "2026-10-03T13:21:06.8522139Z")
    assert "2026-10-03 22:15 KST" in actual["source_addendum"]
    assert actual["marker_sha256"] == "eca874ea9123475d5632c08c90dc072942a296d3badb1f8923c44db48bb3b043"
    assert actual["budget_projector_sha256"] == reader.BUDGET_PROJECTOR_PIN[1]
    assert actual["result"] == {
        "sha256": "d17695351a36522df6b66a1e0fe0860e90410af92c11ec157672a0750ea282ff", "size": 7619,
        "result_fingerprint": "657c19e44d255e6a2849a4f88bb60dab5e5a5710a846cc992abaa3b4e85d2077",
        "recorded_prepared_fingerprint": "14e9357577a916bbeb974853dbe776534082ec16f608b03b20a16e21d0d5c829",
        "registered_config_sha256": reader.TASK5_KEEP_R2_CONFIG_SHA256}
    assert actual["inference_budget_snapshot"] == {"total_seconds": 10800,
        "started_unix": 1790987596.6290615, "expires_unix": 1790998396.6290615,
        "remaining_seconds": 0.0, "wait_seconds": 8742.75936126709,
        "attempts_admitted": 38, "native_resumes": 37, "missing": {}}
    for key in ("terminal_commit", "output_commit", "retained_authority_sha256"):
        assert actual[key] == controls["TASK5_KEEP_R2_BUDGET_CONTROLS"][key]
    assert actual["result_body_verified"] and actual["approval_execution_skipped"]
    assert actual["payload_verification_scope"] == "inference_result_only"
    for key in ("payload_bodies_verified", "ledger_body_verified", "deliverable_bodies_verified", "grading_input_ready",
                "fresh_origin_authentication", "prepared_input_independently_verified", "git_parent_cas_independently_verified",
                "live_read_repeated_here", "replay_authorized"):
        assert actual[key] is False
    assert (actual["status"], actual["exit_code"], actual["cleanup_confirmed"], actual["grade"]) == ("failed", 1, True, None)
    assert actual["writer_acknowledgment"] == "not_established" and actual["recorded_publication_acknowledged"] is True
    assert actual["measurement_limits"] == readout["cells"][7]["current_budget_observation"]["measurement_limits"]
    assert actual["unavailable"] == readout["cells"][7]["current_budget_observation"]["unavailable"]
    for index in (6, 7):
        assert readout["cells"][index]["terminal_details"]["budget"] is None
        assert not readout["cells"][index]["read"]["payload_bodies_verified"]
    assert hashlib.sha256((ci.ROOT / "tasks/codex_budget_pilot/REPORT.md").read_bytes()).hexdigest() == (
        "88a37d8cfdae6c3c05a79db78827bfe2d59fdcd944067e4f6fcd7f387dddae0e")
    report = (ci.ROOT / "tasks/codex_budget_pilot/RETENTION_DIAGNOSTIC_REPORT.md").read_text()
    assert "Both r2 budget observations are consumed" in report
    assert "Both successful Task4 KEEP budgets remain unobserved" in " ".join(report.split())
    for value in actual["inference_budget_snapshot"].values():
        if type(value) in (int, float):
            assert str(value) in report
    with capsys.disabled():
        print("BOUNDARY four exact Task5 configurations/controls; new actual KEEP receipt separated from unchanged historical/FRESH evidence")

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
            "output_objects_sha256": owned._digest(api.terminal["output_objects"]),
            "retained_authority_sha256": owned._digest(api.terminal["authority"])}

    def seal(api):
        revisions(api.fixed)
        api.bind_payload()
        api.seed()
        pin_controls(api)

    def complete(profile):
        cell = intake.controller._adapted_cell(plan["cells"][profile.ordinal])
        return {"run_id": cell["run_id"], "task_id": cell["task_id"], **cell["control"],
            "total_seconds": 10800, "attempt_seconds": 1800, "started_unix": 100.0, "expires_unix": 10900.0,
            "remaining_seconds": 100.0, "wait_seconds": 12.5, "attempts_admitted": 2, "native_resumes": 1}

    default_snapshot = object()

    def make(profile, snapshot=default_snapshot):
        spec = next(spec for spec in profiles if spec[0] is profile)
        fixed = controls[spec[2]]
        revisions(fixed)
        # Reuse the exclusive fixture owner; do not create source roles again.
        api = _task5_fixture(plan, binding=profile, receipt=receipt, with_ledger=True,
                             terminal_head=fixed["terminal_commit"])
        transports.append(api)
        api.fixed, api.profile, api.spec = fixed, profile, spec
        api.files.pop(TASK5_FILE)
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
            (str(tmp_path), api.repo, TOKEN, PRIVATE.decode().strip(), TASK5_FILE, "SECRET-LIKE-ERROR"))
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
        prefix, api = profile.retention_bundle + "-r1-", make(profile)
        with monkeypatch.context() as early:
            early.setattr(retained, "_session", forbidden)
            early.setattr(reader, "_budget_projector", forbidden)
            assert reader.main([], _test_api=api) == 0 and captured(api)["cell_id"] == reader.FRESH_R1.expectation.cell_id
            for other_mode in ("--read", "--observe-terminal"):
                assert reader.main(["--observe-budget", other_mode], _test_api=api) == 2
                assert captured(api)["reason"] == "invalid_arguments"
            wrong_profiles = (reader.FRESH_R1, reader.FRESH_R2, reader.KEEP_R2,
                *(spec[0] for spec in profiles if spec[0] is not profile),
                replace(profile), replace(profile, run_id="1"), replace(profile, execution_job_id=1), object())
            for index, changes in enumerate((
                *({"binding": other} for other in wrong_profiles),
                {"include_budget": 1}, {"expected_reader_sha256": "c" * 64},
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
        print("BOUNDARY both r1 identities/sealed configs and changed/missing current pins refused before imports/session")

    monkeypatch.setenv("HF_TOKEN", TOKEN)  # Authored fixture token, never a credential.
    for profile, producer, _, expected_format, marker_name, config_hash in profiles[:2]:
        prefix, api = profile.retention_bundle + "-r1-", make(profile)
        code, record = cli(api, prefix + "budget")
        assert code == 0, {"boundary": prefix + "first_result_budget_projection", "original_causes": failures[-1:]}
        assert record["format"] == expected_format
        assert record["mode"] == "observe_budget" and record["budget_observation_verified"] is True
        assert record["inference_budget_snapshot"] == {**{key: complete(profile)[key] for key in fields}, "missing": {}}
        assert record["inference_budget_snapshot"]["attempts_admitted"] != record["receipt"]["model_calls"]
        assert record["result"] == {**owned._identity(api.files[intake.RESULT]),
            "result_fingerprint": api.payload["result_fingerprint"],
            "recorded_prepared_fingerprint": api.payload["prepared_fingerprint"],
            "registered_config_sha256": config_hash}
        assert not {"results", "raw_payload", "stderr", "error", "deliverable_files"} & record.keys()
        assert record["supplied_request_binding"]["materialized_grader_source_sha256"] == profile.materialized_grader_source_sha256
        assert record["predecessor"] == producer.PREDECESSOR
        assert (record["status"], record["exit_code"], record["cleanup_confirmed"], record["grade"]) == ("failed", 1, True, None)
        assert record["result_body_verified"] and record["payload_verification_scope"] == "inference_result_only"
        for key in ("payload_bodies_verified", "ledger_body_verified", "deliverable_bodies_verified", "grading_input_ready",
                    "fresh_origin_authentication", "prepared_input_independently_verified", "git_parent_cas_independently_verified",
                    "launch_authorized", "grading_launched", "admission_attempted", "replay_authorized", "invoice_complete"):
            assert record[key] is False
        assert record["writer_acknowledgment"] == "not_established" and record["recorded_publication_acknowledged"] is True
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
            lambda api: api.claim["predecessor"].update(exit_code=137),
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
        for key in ("output_objects_sha256", "retained_authority_sha256"):
            bad = make(profile)
            bad.expected[key] = "0" * 64
            refuse(bad, prefix + key, before_result=True)
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
            lambda value: value.update(ordered_task_ids=[intake.registration.TASK4]),
            lambda value: value["results"][0].update(task_id=intake.registration.TASK4),
            lambda value: value["results"][0].update(observability=[]),
            lambda value: value["results"][0]["observability"].update(task_deadline=None),
            lambda value: value["results"][0]["observability"]["task_deadline"].update(retention_bundle="fresh" if profile.retention_bundle == "keep" else "keep"),
            lambda value: value["results"][0]["observability"]["task_deadline"].update(repetition=2),
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
            print("BOUNDARY " + prefix + "controls/history then RESULT only; tamper refusals and missing/null/zero semantics verified")

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

    # Directly coupled r2 synthetic compatibility, never their delivered tests
    # or either consumed actual observation.
    for profile, _, _, expected_format, marker_name, config_hash in profiles[2:]:
        prefix, api = profile.retention_bundle + "-r2-", make(profile)
        record = read(api, prefix + "budget")
        assert record["format"] == expected_format and record["result"]["registered_config_sha256"] == config_hash
        assert record["inference_budget_snapshot"] == {**{key: complete(profile)[key] for key in fields}, "missing": {}}
        assert (tmp_path / (prefix + "budget") / marker_name).is_file()
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
        print("BOUNDARY both r1 private markers/lost-ack/no-replay; unchanged r2/control-only behavior and historical evidence")

    workflow_contract._assert_retention_execution_workflow_contract()
    workflow_contract._assert_retention_mode_routes()
    workflow = yaml.safe_load((ci.ROOT / ci.WORKFLOW).read_bytes())
    jobs, cells = workflow["jobs"], tuple(plan["order"])
    steps = jobs[ci.PREPARE_JOB]["steps"]
    assert set(workflow_contract._BUDGET_CELLS) == {cells[1], cells[2], cells[3], *cells[4:8]} and len(workflow_contract._BUDGET_CELLS) == 7
    names = ("prepare", "execute", "observe_locator", "read_result", "observe_terminal", "observe_budget")
    mode_cases = 0
    for selected, flags in itertools.product((*cells, "unknown"), itertools.product((False, True), repeat=6)):
        modes = dict(zip(names, flags))
        values = {"inputs." + key: value for key, value in modes.items()}
        values.update({"inputs.cell_id == '" + cell_id + "'": selected == cell_id for cell_id in cells})
        reading, terminal, budget = (modes[name] and sum(flags) == 1 for name in ("read_result", "observe_terminal", "observe_budget"))
        for index in (9, 10, 11, 12, 13, 14):
            expected = ((reading and selected in cells[1:]) if index in (9, 10) else
                        (reading and selected == cells[0]) if index in (11, 12) else
                        ((terminal and selected in cells[1:]) or (budget and selected in workflow_contract._BUDGET_CELLS)))
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
        print(json.dumps({"scope": "synthetic_combined_task5_r1_result_only_budget_observation", "new_profiles": 2,
            "closed_task5_budget_profiles": 4, "mode_cases": mode_cases, "fixed_controls_before_result": True,
            "sealed_r1_configs": True, "missing_null_zero_preserved": True, "private_marker_readback_no_replay": True,
            "unchanged_r2_controls_only_paid_isolation": True, "current_historical_pins_separate": True,
            "actual_keep_r2_receipt_separate_from_synthetic_proof": True,
            "prior_json_fields_fresh_receipt_original_pilot_unchanged": True,
            "network_model_writer_child_paid_effects": len(effects)}, sort_keys=True))
