"""Synthetic retained native Task3 -> real intake/preparation/execution checks.

HTTP, namespace facts and the owned grader child are explicit local fixtures.
No provider, native runner, judge, live storage or kernel-support proof occurs.
"""

from dataclasses import asdict, replace
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from types import SimpleNamespace

import httpx
import pytest

import gpt54_time_budget_grading_execution as subject
from core.agentic_v2_preregistration import seal
from core.result_fingerprint import validate_inference_result_fingerprint
from gpt54_prepared_input_attestation import _identity
from .test_time_budget_native_grading_intake import (
    TOKEN, PRIVATE, NAMES, case, dual_roots, handoff_source_seed, handoff_sources,
)
from .test_time_budget_grading_preparation import (
    _execution_case, _execution_cli, _execution_direction, _execution_transport,
)

intake, preparation = subject.native_intake, subject.preparation
_REAL_RUN, _REAL_POPEN = subprocess.run, subprocess.Popen


@pytest.fixture
def offline(monkeypatch, handoff_sources, dual_roots):
    from huggingface_hub import HfApi, constants
    from core import azure_ai_clients, rubric_loader
    from core.time_budget_observation_deadline import TimeBudgetObservation

    denied, prepared = [], []

    def forbidden(*args, **kwargs):
        denied.append(True)
        raise AssertionError("offline native grading compatibility crossed its fixture boundary")

    for owner, names in (
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (subprocess, ("Popen", "check_call", "check_output")), (os, ("system",)),
        (HfApi, ("create_repo", "create_commit", "upload_file", "delete_file", "delete_repo")),
        (rubric_loader, ("snapshot_download", "hf_hub_download", "HfApi")),
        (intake.native, ("prepare_and_claim", "execute", "retain")),
        (intake.native.observation, ("run_codex_observation",)),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    for constructor in (azure_ai_clients.AzureAIClientFactory, azure_ai_clients.OpenAI,
                        azure_ai_clients.AzureOpenAI, azure_ai_clients.DefaultAzureCredential,
                        subject.step8.Grader, TimeBudgetObservation):
        monkeypatch.setattr(constructor, "__init__", forbidden)

    def local_git(command, **kwargs):
        assert command[:2] == ["/usr/bin/git", "--no-replace-objects"]
        position = command.index("-C")
        assert Path(command[position + 1]) in {handoff_sources.runtime, handoff_sources.frozen,
                                              dual_roots["runtime"], dual_roots["frozen"]}
        assert command[position + 2] in {"rev-parse", "config", "ls-tree", "cat-file"}
        assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == "" and kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        assert "HF_TOKEN" not in kwargs["env"] and kwargs["timeout"] == 60
        kwargs["timeout"] = 30  # Same named guarded local-Git seam as the accepted intake proof.
        with monkeypatch.context() as process:
            process.setattr(subprocess, "Popen", _REAL_POPEN)
            return _REAL_RUN(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", local_git)
    ordinary_sleep = time.sleep

    def no_online_sleep(seconds):
        if not constants.HF_HUB_OFFLINE:
            forbidden()
        ordinary_sleep(seconds)

    monkeypatch.setattr(time, "sleep", no_online_sleep)
    monkeypatch.setattr(constants, "HF_HUB_DISABLE_TELEMETRY", True)
    monkeypatch.setattr(constants, "HF_HUB_OFFLINE", True)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    for key in intake.OTHER_CREDENTIALS | {"HF_TOKEN"}:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(intake.native.originals, "PARQUET_PIN", _identity(handoff_sources.parquet.read_bytes()))
    monkeypatch.setattr(intake.native.originals, "STEP0_PIN", _identity(handoff_sources.step0.read_bytes()))
    real_prepare = preparation.prepare_observation_grading

    def observe_prepare(*args, **kwargs):
        assert not any(os.environ.get(key) for key in intake.OTHER_CREDENTIALS | {"HF_TOKEN"})
        prepared.append(kwargs)
        return real_prepare(*args, **kwargs)

    monkeypatch.setattr(preparation, "prepare_observation_grading", observe_prepare)
    ordinary_readlink = os.readlink
    namespaces = {"/proc/self/ns/" + name: f"{name}:[91000{index}]"
                  for index, name in enumerate(("pid", "mnt", "user"), 1)}

    def synthetic_namespace(path, *args, **kwargs):
        return namespaces[str(path)] if str(path) in namespaces else ordinary_readlink(path, *args, **kwargs)

    monkeypatch.setattr(os, "readlink", synthetic_namespace)
    yield SimpleNamespace(denied=denied, prepared=prepared)
    assert denied == []


def _retained_transport(case, monkeypatch, *, wrong_revision=False):
    assert not {"source_repo_id", "source_revision", "source_identity_document_sha256"} & case.payload.keys()
    data = intake.reader._bytes(case.payload)  # Actual native _capture output from the accepted fixture.
    completion = case.request["completion"]
    completion.update(result_identity=_identity(data), result_fingerprint=validate_inference_result_fingerprint(case.payload))
    revision, target = completion["output_commit"], intake.reader.metadata.TARGET
    prefix, _, _ = intake.native.shared._namespace(intake.CELL)
    bodies = {f"/datasets/{target}/raw/{revision}/{prefix}/result/{intake.native.observation.RESULT}": data,
        **{f"/datasets/{target}/raw/{revision}/{prefix}/result/upload/{name}": value for name, value in case.files.items()}}
    calls = []

    class Transport(httpx.BaseTransport):
        def __init__(self, **kwargs):
            assert kwargs == {"retries": 0, "trust_env": False}

        def handle_request(self, request):
            calls.append(request)
            assert len(calls) <= 4 and request.method == "GET" and request.headers["accept-encoding"] == "identity"
            assert request.headers["authorization"] == "Bearer " + TOKEN and "HF_TOKEN" not in os.environ
            assert all(0 < seconds <= 60 for seconds in request.extensions["timeout"].values())
            if len(calls) == 1:
                assert request.url.path == f"/api/datasets/{target}/revision/{revision}"
                body = intake.reader._bytes({"id": target, "private": True, "sha": "9" * 40 if wrong_revision else revision})
            else:
                body = bodies[request.url.path]
            return httpx.Response(200, stream=httpx.ByteStream(body), request=request)

    monkeypatch.setattr(httpx, "HTTPTransport", Transport)
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    request = intake.reader._bytes(case.request)
    return data, calls, {"request_json": request.decode(), "expected_request_sha256": _identity(request)["sha256"]}


def _arguments(case, native, tmp_path, monkeypatch):
    arguments = subject._native_arguments(native)
    assert asdict(arguments["observation"]) == case.marker["observation"]
    assert arguments["expected_input_binding"] == case.marker["inputs"]
    store = tmp_path / "once-only-local-store"
    store.mkdir(mode=0o700)
    arguments.update(attempt_store=store, destination=tmp_path / "private-intake" / "grade-attempt",
        direction_file=tmp_path / "direction.json", expected_direction_sha256="0" * 64,
        expected_execution_context_sha256=subject.execution_context_sha256())
    monkeypatch.setattr(subject, "time", SimpleNamespace(time=lambda: 1000))
    direction = _execution_direction(case.seed.plan, arguments)
    return arguments, direction


def _child(arguments, monkeypatch, *, mode, record_property):
    """Only the owned-child boundary is synthetic; F serializers/checks are real."""
    from core.cost_receipts import CostReceipt, ledger_reference
    from core.grader import ItemGrade, TaskGrade
    from core.rubric_loader import RubricLoader
    from core.task_checkpoint import TaskProgressDraft, build_progress, write_checkpoint

    calls = []

    def process(_self, command, *, ownership, **options):
        calls.append(tuple(command))
        record_property("child_operation", "bound_local_claim_command_environment_and_synthetic_ownership")
        key = subject._observation_key(arguments["observation"])
        claim_path = arguments["attempt_store"] / (key + ".json")
        claim = json.loads(claim_path.read_bytes())
        binding = claim["binding"]
        assert claim["state"] == "consumed_before_child_never_reusable" and claim["attempt"] == 1
        assert claim["direction_sha256"] == arguments["expected_direction_sha256"] and command == binding["command"]
        assert len(list(arguments["attempt_store"].iterdir())) == 1
        batch = Path(binding["working_directory"])
        output = batch.parent.parent
        assert command[1] == str(batch / "step8_grade.py") and options["cwd"] == batch
        assert command[2] == subject.NATIVE_RUN and command[command.index("--tasks") + 1] == subject.NATIVE_TASK
        assert command[command.index("--source-experiment-id") + 1] == subject.NATIVE_RUN
        assert command[command.index("--limit") + 1] == "1" and "--force" not in command and "--resume" not in command
        assert (batch / "step8_grade.py").read_bytes() == (arguments["frozen_grader_root"] / "batch-runner/step8_grade.py").read_bytes()
        assert options["timeout"] == 14520 and options["env"]["GRADER_TIME_BUDGET_SEC"] == "14400"
        assert options["env"]["HF_HUB_OFFLINE"] == options["env"]["HF_DATASETS_OFFLINE"] == "1"
        assert not {"HF_TOKEN", "GITHUB_TOKEN", "GITHUB_OUTPUT", "PYTHONPATH", "PYTHONHOME"} & options["env"].keys()
        assert options["stdout"] == options["stderr"] == subprocess.DEVNULL
        assert os.fstat(options["pass_fds"][0]).st_ino == claim_path.stat().st_ino
        owner_path, owner_binding = ownership
        assert owner_binding["cell_id"] == key and owner_binding["stage"] == "time_budget_f_grading"
        owner_path.write_bytes(subject._encoded({**owner_binding, "phase": "reaped", "tree_reaped": True, "owner_reaped": True}))

        # Import the staged, byte-verified F Step8, not a fake success result.
        record_property("child_operation", "import_verified_F_step8")
        spec = importlib.util.spec_from_file_location("synthetic_frozen_step8", batch / "step8_grade.py")
        frozen = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, frozen)
        spec.loader.exec_module(frozen)
        config_path = Path(command[command.index("--config") + 1])
        config = json.loads(config_path.read_bytes())
        record_property("child_operation", "F_validate_grading_config_and_compute_source_hash")
        frozen.validate_grading_config(config)
        actual_hash = frozen.compute_grader_source_hash(config_path, config, batch_root=batch)
        assert actual_hash == binding["grader"]["materialized_source_sha256"] != subject.registration.FROZEN_TEMPLATE_SHA256
        with monkeypatch.context() as location:
            location.chdir(batch)
            record_property("child_operation", "F_load_experiment_and_local_input")
            experiment = frozen.load_experiment_yaml(subject.NATIVE_RUN)
            payload = frozen.load_local_inference_results()
        assert experiment.experiment_id == subject.NATIVE_RUN and experiment.data_filter.task_ids == [subject.NATIVE_TASK]
        assert experiment.condition_a.name == "codex" and experiment.execution.mode == "codex_foundry"
        assert experiment.validate() == []
        record_property("child_operation", "F_source_identity_and_task_selection")
        repo, revision = frozen.resolve_source_inference_identity(payload, "2.0")
        assert (repo, revision) == (binding["grading_input_origin"]["source_repo_id"], binding["grading_input_origin"]["source_revision"])
        selected, scope = frozen.filter_tasks_for_config(payload, config, tasks_csv=subject.NATIVE_TASK, limit=1)
        assert [row["task_id"] for row in selected] == [subject.NATIVE_TASK]
        loader = RubricLoader(config["rubric"]["repo_id"], config["rubric"]["revision"], str(output / preparation.CACHE))
        record_property("child_operation", "load_frozen_rubric_and_construct_synthetic_child_output")
        rubric = loader.load(subject.NATIVE_TASK)
        task = TaskGrade(task_id=subject.NATIVE_TASK, sector=rubric.sector, occupation=rubric.occupation,
            items=[ItemGrade(rubric_item_id=item.rubric_item_id, criterion=item.criterion, max_score=item.score,
                awarded_score=0, verdict="fail", decided_by="precheck", required=None,
                evidence="synthetic child output only; not a judge result", precheck_pattern_id="file_exists_or_name")
                for item in rubric.rubric_items], total_awarded=0, total_max=0, pct=0, critical_fail=False,
            gold_referenced=False, judge_call_count=0, precheck_count=len(rubric.rubric_items), judge_total_latency_ms=0,
            judge_input_tokens=0, judge_output_tokens=0, usage_complete=False)
        partial = mode in {"partial", "timeout", "sidecar"}
        rows = [] if partial else [frozen._task_to_dict(task, grading_wall_time_ms=0.0)]
        for row in rows:
            row["grading_cost"] = CostReceipt.unavailable().as_dict()
        grade = frozen._build_grade_payload(exp_name=subject.NATIVE_RUN, inf_results=payload, config=config,
            config_hash=frozen.hash_config(str(config_path)), loader=loader, prompt_version=config["prompt"]["version"],
            task_dicts=rows, grader_source_hash=actual_hash, source_inference_repo_id=repo, source_inference_revision=revision,
            azure_ai_runtime_fingerprint="f" * 64, azure_ai_routes=[{"workload": "grader", "runtime_fingerprint": "f" * 64,
                "profile": "direct-v1", "endpoint_kind": "direct-v1"}], run_status="partial" if partial else "diagnostic",
            expected_task_ids=[subject.NATIVE_TASK], source_experiment_id=subject.NATIVE_RUN,
            renderer_fingerprint={"libreoffice_binary": "synthetic", "libreoffice_version": "synthetic", "pymupdf_version": "synthetic"})
        record_property("child_operation", "F_output_filename_ledger_and_checkpoint")
        path = Path(binding["grade_path"])
        assert path == (batch / frozen.resolve_grade_output_path(config, experiment_id=subject.NATIVE_RUN,
            judge_slug=frozen._judge_slug(config["judge"]["model"]), config_hash=frozen.hash_config(str(config_path)),
            rubric_sha=config["rubric"]["revision"], rubric_short_sha=config["rubric"]["revision"][:7],
            prompt_version=config["prompt"]["version"], inference_sha=revision, grader_source_hash=actual_hash,
            diagnostic_task_scope_sha=frozen._ordered_task_ids_sha256([subject.NATIVE_TASK]))).resolve()
        ledger = path.with_name(path.stem + ".cost_ledger.jsonl")
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_bytes(b"")  # Explicit synthetic no-call ledger, never actual usage.
        grade["cost_ledger"] = ledger_reference(ledger.relative_to(batch.parent), _identity(b"")["sha256"])
        if partial:
            write_checkpoint(path, build_progress(task_id=subject.NATIVE_TASK, grader_source_hash=actual_hash,
                rubric_item_ids=[item.rubric_item_id for item in rubric.rubric_items], draft=TaskProgressDraft()))
        if mode == "grade_task":
            grade["tasks"][0]["task_id"] = subject.FIRST_TASK
            grade["expected_ordered_task_ids_sha256"] = frozen._ordered_task_ids_sha256([subject.FIRST_TASK])
        record_property("child_operation", "F_grade_schema_and_private_save")
        frozen.validate_grade_payload(grade, json.loads((batch / "schemas/grade.schema.json").read_bytes()))
        frozen._save_json(path, grade)
        if mode == "sidecar":
            ledger.write_bytes(b"synthetic ledger drift\n")
        if mode == "timeout":
            record_property("child_operation", "synthetic_child_timeout_14520_seconds")
            raise subprocess.TimeoutExpired(command, options["timeout"])
        return subprocess.CompletedProcess(command, 1 if partial else 0)

    monkeypatch.setattr(subject.owned.LocalTransport, "process", process)
    return calls


@pytest.mark.parametrize("scenario", [
    "native", "legacy_v2", "task", "r2", "condition", "step0_missing", "step0_bytes", "step0_overlap",
    "origin_without_intake", "origin_revision", "origin_receipt", "derived_bytes", "frozen_source", "direction",
    "partial", "timeout", "grade_task", "sidecar",
])
def test_native_task3_frozen_grading_compatibility(case, offline, monkeypatch, tmp_path, dual_roots,
                                                capsys, record_property, scenario):
    if scenario == "legacy_v2":
        arguments, marker, _ = _execution_case(case.seed, dual_roots, tmp_path, monkeypatch)
        calls = _execution_transport(arguments, monkeypatch)
        with pytest.raises(TypeError, match="unexpected keyword argument 'step0_manifest'"):
            subject.execute_first_observation_grading(case.seed.plan, **arguments, step0_manifest=case.seed.step0)
        assert list(arguments["attempt_store"].iterdir()) == [] and calls == []
        assert subject.main(_execution_cli(arguments, tmp_path)) == 0
        assert json.loads(capsys.readouterr().out) == {"terminal_reason": "completed", "retry_allowed": False}
        result = json.loads((arguments["destination"] / subject.RESULT).read_bytes())
        assert result["binding"]["result"] == marker["result"] and "grading_input_origin" not in result["binding"]
        assert "step0_manifest" not in result["binding"]["paths"] and len(calls) == 1
        record_property("bounded_outcome", "legacy V2 API/CLI completed; Step0 argument refused; one synthetic child")
        return

    data, http_calls, request = _retained_transport(case, monkeypatch, wrong_revision=scenario == "origin_revision")
    derived_root = tmp_path / "private-intake" / "grading-only-input"
    if scenario == "origin_revision":
        with pytest.raises(subject.GradingExecutionRefused, match="^native_grading_input_refused_retain_partial_state$"):
            with subject.prepare_native_task3_grading_execution(**request, execution_input_directory=derived_root):
                pytest.fail("mismatched immutable publication admitted")
        assert len(http_calls) == 1 and offline.prepared == [] and not derived_root.exists()
        assert subject._NATIVE_INTAKES == {} and capsys.readouterr() == ("", "")
        record_property("bounded_outcome", "immutable origin metadata mismatch refused before preparation or grade claim")
        return

    record_property("operation", "accepted_intake_and_F_preparation_then_native_grading_input_staging")
    with subject.prepare_native_task3_grading_execution(**request, execution_input_directory=derived_root) as native:
        assert len(http_calls) == 4 and len(offline.prepared) == 1 and "HF_TOKEN" not in os.environ
        record_property("operation", "independent_direction_with_real_preparation_checks")
        arguments, direction = _arguments(case, native, tmp_path, monkeypatch)
        original = {path: _identity(path.read_bytes()) for root in (case.paths["hydration_root"], case.paths["destination"])
                    for path in root.rglob("*") if path.is_file()}
        assert case.seed.step0.stat().st_size == 218405 and arguments["expected_input_binding"]["step0_manifest"] == _identity(case.seed.step0.read_bytes())
        derived = json.loads((derived_root / preparation.RESULT).read_bytes())
        assert (case.paths["hydration_root"] / intake.native.observation.RESULT).read_bytes() == data
        assert (case.paths["destination"] / preparation.RESULT).read_bytes() == data
        origin = direction["binding"]["grading_input_origin"]
        assert origin["original_result_identity"] == _identity(data)
        assert origin["original_result_fingerprint"] == validate_inference_result_fingerprint(case.payload)
        assert origin["derived_result_identity"] == _identity((derived_root / preparation.RESULT).read_bytes())
        assert origin["derived_result_fingerprint"] == validate_inference_result_fingerprint(derived) != origin["original_result_fingerprint"]
        additions = {"source_repo_id", "source_revision", "source_identity_document_sha256"}
        assert {**{key: value for key, value in derived.items() if key not in additions},
                "result_fingerprint": case.payload["result_fingerprint"]} == case.payload
        assert (derived["source_repo_id"], derived["source_revision"]) == (intake.reader.metadata.TARGET, case.request["completion"]["output_commit"])
        calls = _child(arguments, monkeypatch, mode=scenario, record_property=record_property)
        changed = None
        expected_error = "grading_execution_refused_retain_any_claim_or_partial_state"
        if scenario in {"task", "r2", "condition"}:
            replacements = {"task": {"task_id": case.seed.task_ids[1]}, "r2": {"run_id": "gpt54_time_budget_v1_codex_r2", "repeat": 2},
                            "condition": {"run_id": "gpt54_time_budget_v1_v2_r1", "condition": "sandbox_v2"}}
            arguments["observation"] = replace(arguments["observation"], **replacements[scenario])
            expected_error = "native_r1_task3_only"
        elif scenario == "step0_missing":
            arguments["step0_manifest"] = None
            expected_error = "native_whole_step0_required"
        elif scenario == "step0_bytes":
            case.seed.step0.write_bytes(case.seed.step0.read_bytes()[:-1] + b"\n")
        elif scenario == "step0_overlap":
            arguments["step0_manifest"] = arguments["destination"]
            expected_error = "grading_path_overlap"
        elif scenario == "origin_without_intake":
            arguments["native_preparation"] = subject.NativeGradingPreparation()
            expected_error = "current_authenticated_native_intake_required"
        elif scenario == "origin_receipt":
            changed = case.paths["hydration_root"] / intake.READY
            receipt = json.loads(changed.read_bytes())
            receipt["output_commit"] = "9" * 40
            changed.write_bytes(subject._encoded(receipt))
        elif scenario == "derived_bytes":
            changed = derived_root / preparation.RESULT
            derived["source_revision"] = "9" * 40
            derived["result_fingerprint"] = subject.inference_result_fingerprint(derived)
            changed.write_bytes(subject._encoded(derived))
        elif scenario == "frozen_source":
            arguments["expected_grader_source_sha"] = "f" * 40
        elif scenario == "direction":
            direction["expires_at"] = 999
            direction_data = subject._encoded(direction)
            arguments["direction_file"].write_bytes(direction_data)
            arguments["expected_direction_sha256"] = _identity(direction_data)["sha256"]
            expected_error = "direction_admission_window_refused"

        if scenario == "native":
            legacy = {key: value for key, value in arguments.items() if key not in {"native_preparation", "step0_manifest"}}
            with pytest.raises(subject.GradingExecutionRefused, match="^first_registered_v2_observation_only$"):
                subject.execute_first_observation_grading(case.seed.plan, **legacy)
            assert calls == [] and list(arguments["attempt_store"].iterdir()) == []
            monkeypatch.setenv("GITHUB_TOKEN", "synthetic_step_token_not_for_child")
        if scenario in {"native", "partial", "timeout"}:
            record_property("operation", "shared_executor_native_entry")
            result = subject.execute_native_task3_grading(case.seed.plan, **arguments)
            assert result["terminal_reason"] == {"native": "completed", "partial": "failed", "timeout": "timeout"}[scenario]
            assert result["retry_allowed"] is False and result["cleanup_confirmed"] is True
            assert result["timed_out"] is (scenario == "timeout") and len(calls) == 1
            assert result["binding"]["grading_input_origin"] == origin
            assert result["binding"]["result"]["file"]["sha256"] == _identity(data)["sha256"]
            assert result["binding"]["inputs"]["step0_manifest"]["size"] == 218405
            assert result["usage"]["complete"] is False and result["usage"]["invoice_complete"] is False
            grade = json.loads((arguments["destination"] / "grade.json").read_bytes())
            assert (grade["source_inference_repo_id"], grade["source_inference_revision"]) == (derived["source_repo_id"], derived["source_revision"])
            assert grade["expected_ordered_task_ids_sha256"] == subject.step8._ordered_task_ids_sha256([subject.NATIVE_TASK])
            assert any("/_progress/" in row["path"] for row in result["sidecar_files"]) is (scenario != "native")
            for row in result["sidecar_files"]:
                assert _identity((arguments["destination"] / row["path"]).read_bytes()) == {key: row[key] for key in ("size", "sha256")}
        else:
            if scenario == "grade_task":
                expected_error = "grade_scope_mismatch"
            record_property("operation", "shared_executor_native_refusal_case")
            with pytest.raises(subject.GradingExecutionRefused) as refused:
                subject.execute_native_task3_grading(case.seed.plan, **arguments)
            assert refused.value.args == (expected_error,)
            assert len(calls) == (1 if scenario in {"grade_task", "sidecar"} else 0)
            assert not (arguments["destination"] / subject.RESULT).exists()

        if calls:
            claim = arguments["attempt_store"] / (subject._observation_key(arguments["observation"]) + ".json")
            before = claim.read_bytes()
            alternate = arguments["destination"].with_name("unused-alternate")
            with pytest.raises(subject.GradingExecutionRefused, match="^grading_attempt_already_claimed$"):
                subject.execute_native_task3_grading(case.seed.plan, **{**arguments, "destination": alternate})
            assert len(calls) == 1 and claim.read_bytes() == before and len(list(arguments["attempt_store"].iterdir())) == 1
            assert not alternate.exists() and not alternate.with_name(alternate.name + subject.RESERVATION_SUFFIX).exists()
        else:
            assert list(arguments["attempt_store"].iterdir()) == [] and not arguments["destination"].exists()
        assert all(_identity(path.read_bytes()) == identity for path, identity in original.items() if path != changed)
        assert len(http_calls) == 4 and offline.denied == []
        assert all(TOKEN.encode() not in path.read_bytes() for path in derived_root.rglob("*") if path.is_file())
        assert capsys.readouterr() == ("", "")
        record_property("bounded_outcome", json.dumps({"scenario": scenario, "synthetic_http_gets": len(http_calls),
            "synthetic_child_calls": len(calls), "original_result": _identity(data), "derived_result": origin["derived_result_identity"],
            "whole_synthetic_step0_bytes": 218405, "frozen_step8_seconds": 14400, "child_seconds": 14520,
            "host_or_private_task_proof": False}, sort_keys=True))
    assert subject._NATIVE_INTAKES == {}
    with pytest.raises(subject.GradingExecutionRefused, match="^current_authenticated_native_intake_required$"):
        subject._native_intake(native)
