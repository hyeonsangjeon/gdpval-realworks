"""Synthetic one-observation F materialization, not a judge or private-data run."""

import json
import os
import socket
import subprocess
from dataclasses import asdict, replace
from pathlib import Path

import pytest

import gpt54_time_budget_comparison as registration
import gpt54_time_budget_grading_preparation as preparation
import step8_grade
from core.agentic_v2_preregistration import seal
from core.result_fingerprint import inference_result_fingerprint
from core.rubric_loader import RubricLoader
from core.time_budget_observation_deadline import TIMEOUT, ObservationIdentity, TimeBudgetObservation
from gpt54_comparison_preflight import GRADER, _canonical_json, load_plan
from gpt54_prepared_input_attestation import _identity
from .test_gpt54_time_budget_comparison import (
    _handoff_arguments, dual_roots, handoff_source_seed, handoff_sources,
)

_REAL_RUN, _REAL_POPEN = subprocess.run, subprocess.Popen


@pytest.fixture(autouse=True)
def offline(monkeypatch, handoff_sources, dual_roots):
    """Permit only guarded local object reads; no successful verdict is mocked."""
    from core import azure_ai_clients, rubric_loader

    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        pytest.fail("grading preparation attempted provider/grader/network/admission")

    for owner, names in ((socket.socket, ("connect", "connect_ex")),
                         (socket, ("create_connection",)),
                         (subprocess, ("run", "Popen", "check_call", "check_output")),
                         (os, ("system",)),
                         (rubric_loader, ("snapshot_download", "hf_hub_download", "HfApi"))):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    for constructor in (azure_ai_clients.AzureAIClientFactory, azure_ai_clients.OpenAI,
                        azure_ai_clients.AzureOpenAI, azure_ai_clients.DefaultAzureCredential,
                        step8_grade.Grader, TimeBudgetObservation):
        monkeypatch.setattr(constructor, "__init__", forbidden)

    def local_git(command, **kwargs):
        assert command[:2] == ["/usr/bin/git", "--no-replace-objects"]
        position = command.index("-C")
        assert Path(command[position + 1]) in {
            handoff_sources.runtime, handoff_sources.frozen,
            dual_roots["runtime"], dual_roots["frozen"], dual_roots["substitute"],
        }
        assert command[position + 2] in {"rev-parse", "config", "ls-tree", "cat-file"}
        assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == ""
        assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1" and kwargs["timeout"] == 60
        with monkeypatch.context() as process:
            process.setattr(subprocess, "Popen", _REAL_POPEN)
            return _REAL_RUN(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", local_git)
    yield calls
    assert calls == []


def _store_result(arguments, payload):
    payload["result_fingerprint"] = inference_result_fingerprint(payload)
    data = _canonical_json(payload).encode()
    arguments["result_path"].write_bytes(data)
    arguments["expected_result_identity"] = _identity(data)


def _case(seed, tmp_path, *, condition="sandbox_v2", status="success"):
    # Reuse the accepted preparer's genuine input/source checks to create the
    # expected identity. This is synthetic fixture setup, not a prior selector.
    task_index = next(index for index, row in enumerate(seed.rows) if row["reference_files"])
    handoff = _handoff_arguments(seed, tmp_path, condition=condition, task_index=task_index)
    prepared = registration.prepare_observation_handoff(seed.plan, **handoff)
    observation = ObservationIdentity(**prepared["observation"])
    original = tmp_path / "synthetic-result"
    original.mkdir()
    upload = original / "upload"
    upload.mkdir()
    records = []
    if status == "success":
        role = f"deliverable_files/{observation.task_id}/synthetic.txt"
        path = upload / role
        path.parent.mkdir(parents=True)
        path.write_bytes(b"Explicitly synthetic output; no model or score.\n")
        records.append({"path": role, **_identity(path.read_bytes())})
    payload = {
        "experiment_id": observation.run_id, "condition": observation.condition,
        "execution_mode": "codex" if condition == "codex" else "agentic_sandbox_v2",
        "model": seed.plan["shared"]["model"]["deployment"], "source": seed.plan["shared"]["dataset"]["repo_id"],
        "time_budget_observation": {
            "policy": "time_budget_observation_deadline_v1", "identity": asdict(observation),
            "admitted": True, "terminal_reason": "completed" if status == "success" else "failed",
            "cleanup_complete": status == "success", "host_reusable": status == "success",
            "remote_cancellation_confirmed": False, "remote_billing_bound": False,
        },
        "results": [{"task_id": observation.task_id, "status": status,
                     "error": None if status == "success" else "synthetic_missing_output",
                     "retried": False, "deliverable_files": [item["path"] for item in records],
                     "deliverable_file_records": records}],
    }
    arguments = {key: value for key, value in handoff.items()
                 if key not in {"run_id", "task_id", "destination"}}
    arguments.update(observation=observation, expected_input_binding=prepared["inputs"],
        result_path=original / "result.json", deliverables_root=upload,
        destination=tmp_path / "publications" / "one-grading")
    _store_result(arguments, payload)
    return arguments, payload, prepared


def _unpublished(arguments):
    output = arguments["destination"]
    assert not output.exists()
    assert not output.with_name(output.name + preparation.RESERVATION_SUFFIX).exists()


@pytest.mark.parametrize("condition,reason,valid", [
    pytest.param("sandbox_v2", "running", False, id="v2-running-refused"),
    pytest.param("codex", "pending", False, id="codex-pending-refused"),
    pytest.param("codex", "unknown-terminal", False, id="codex-unknown-refused"),
    pytest.param("sandbox_v2", "completed", True, id="v2-completed-error"),
    pytest.param("codex", "failed", True, id="codex-failed-error"),
    pytest.param("sandbox_v2", "cancelled", True, id="v2-cancelled-error"),
    pytest.param("codex", "abandoned", True, id="codex-abandoned-error"),
    pytest.param("sandbox_v2", TIMEOUT, True, id="v2-timeout-error"),
])
def test_time_budget_f_grading_preparation_terminal_reason(
    handoff_sources, tmp_path, offline, condition, reason, valid,
):
    arguments, payload, _ = _case(handoff_sources, tmp_path, condition=condition, status="error")
    payload["time_budget_observation"]["terminal_reason"] = reason
    _store_result(arguments, payload)  # Coherent identity does not prove terminal semantics.
    result_data = arguments["result_path"].read_bytes()
    assert arguments["expected_result_identity"] == _identity(result_data)
    assert payload["result_fingerprint"] == inference_result_fingerprint(payload)
    if not valid:
        with pytest.raises(preparation.GradingPreparationRefused, match="^terminal_observation_required$"):
            preparation.prepare_observation_grading(handoff_sources.plan, **arguments)
        _unpublished(arguments)
    else:
        marker = preparation.prepare_observation_grading(handoff_sources.plan, **arguments)
        output = arguments["destination"]
        assert marker == json.loads((output / preparation.READY).read_bytes())
        assert marker["result"]["terminal_reason"] == reason
        assert marker["result"]["status"] == "error"
        assert marker["result_identity"] == arguments["expected_result_identity"]
        assert (output / preparation.RESULT).read_bytes() == result_data
        assert payload["results"][0]["error"] == "synthetic_missing_output"
        assert payload["results"][0]["deliverable_file_records"] == []
        assert payload["time_budget_observation"]["cleanup_complete"] is False
        assert payload["time_budget_observation"]["host_reusable"] is False
        config = json.loads((output / preparation.CONFIG).read_bytes())
        materialized = step8_grade.compute_grader_source_hash(
            config_path=output / preparation.CONFIG, config=config, batch_root=output / "source/batch-runner")
        assert materialized == marker["grader"]["materialized_source_sha256"] != registration.FROZEN_TEMPLATE_SHA256
        assert (output / marker["grader"]["entrypoint"]).read_bytes() == (
            handoff_sources.frozen / "batch-runner/step8_grade.py").read_bytes()
        assert marker["grader"]["execution_source"] == "source"
        assert marker["launch_allowed"] is marker["execution_enabled"] is False
    assert arguments["result_path"].read_bytes() == result_data
    assert offline == []


@pytest.mark.parametrize("condition,status", [
    ("sandbox_v2", "success"), ("codex", "success"),
    ("sandbox_v2", "error"), ("codex", "error"),
])
def test_time_budget_f_grading_preparation_valid(handoff_sources, tmp_path, condition, status):
    seed = handoff_sources
    arguments, payload, expected = _case(seed, tmp_path, condition=condition, status=status)
    frozen_before = {role: (seed.frozen / role).read_bytes()
                     for role in (GRADER, "batch-runner/step8_grade.py", "batch-runner/core/codex_runner.py")}
    marker = preparation.prepare_observation_grading(seed.plan, **arguments)
    output = arguments["destination"]
    assert marker == json.loads((output / preparation.READY).read_bytes())
    assert set(marker) == {"preparation_version", "observation", "input_binding_sha256", "result_identity",
        "runtime_source", "frozen_grader_source", "config", "grading_policy", "grading_attempt",
        "launch_allowed", "execution_enabled", "reservation", "registration_file", "preparation_helper",
        "grader", "inputs", "result", "files", "evidence_boundary"}
    assert marker["observation"] == expected["observation"]
    assert marker["inputs"] == expected["inputs"]
    assert marker["result_identity"] == arguments["expected_result_identity"]
    assert marker["result"]["status"] == status
    assert (output / preparation.RESULT).read_bytes() == arguments["result_path"].read_bytes()
    assert marker["grading_policy"] == {"attempts_per_resulting_observation": 1,
        "failed_or_missing_outcomes": "retain", "regrade_for_score": False}
    assert marker["grading_attempt"] == 1
    assert marker["launch_allowed"] is marker["execution_enabled"] is False
    assert marker["evidence_boundary"] == "model_free_grading_preparation_not_attempt_or_execution_authority"
    assert marker["grader"]["entrypoint"] == "source/batch-runner/step8_grade.py"
    assert marker["grader"]["execution_source"] == "source"
    assert marker["grader"]["config_path"] == str(output / preparation.CONFIG)
    assert marker["config"] == {"path": preparation.CONFIG, **_identity((output / preparation.CONFIG).read_bytes())}
    config = json.loads((output / preparation.CONFIG).read_bytes())
    template = load_plan(seed.frozen / GRADER)
    assert config["judge"] == template["judge"]
    assert config["prompt"] == template["prompt"]
    assert config["grader"] == template["grader"]
    assert config["rubric"] == {**template["rubric"], "revision": seed.plan["shared"]["grading"]["rubric_revision"],
                                "cache_dir": "../data/gdpval-local"}
    assert {key: value for key, value in config.items() if key != "rubric"} == {
        key: value for key, value in template.items() if key != "rubric"}
    # Both are actual whole closures. Merely choosing similar judge parameters
    # does not make the materialized path/config the old template identity.
    frozen_hash = step8_grade.compute_grader_source_hash(
        config_path=output / "source" / GRADER, config=template, batch_root=output / "source/batch-runner")
    assert frozen_hash == "37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce"
    materialized = step8_grade.compute_grader_source_hash(
        config_path=output / preparation.CONFIG, config=config, batch_root=output / "source/batch-runner")
    assert materialized == marker["grader"]["materialized_source_sha256"] != frozen_hash
    assert step8_grade.compute_grader_source_hash(config_path=seed.runtime / GRADER,
        config=template, batch_root=seed.runtime / "batch-runner") != frozen_hash
    for role, data in frozen_before.items():
        assert (seed.frozen / role).read_bytes() == data
        assert (output / "source" / role).read_bytes() == data
    assert (output / "source/batch-runner/core/codex_runner.py").read_bytes() != (
        seed.runtime / "batch-runner/core/codex_runner.py").read_bytes()
    assert not (output / "source/.git").exists()
    assert not (output / "source/.github").exists()
    assert not (output / "source" / preparation.HELPER).exists()
    rubric = config["rubric"]
    loader = RubricLoader(rubric["repo_id"], rubric["revision"], str(output / preparation.CACHE))
    snapshot = output / preparation.CACHE / loader.SNAPSHOT_DIRNAME / rubric["revision"]
    loader._validate_snapshot(snapshot)
    assert (snapshot / "data/registered.parquet").read_bytes() == seed.parquet.read_bytes()
    assert all(_identity((output / role).read_bytes()) == identity for role, identity in marker["files"].items())
    assert {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()} == {
        *marker["files"], preparation.READY}
    reservation = output.with_name(output.name + preparation.RESERVATION_SUFFIX)
    assert _identity(reservation.read_bytes()) == {key: marker["reservation"][key] for key in ("sha256", "size")}
    assert json.loads(reservation.read_bytes())["intent"]["observation"] == marker["observation"]
    with pytest.raises(preparation.GradingPreparationRefused, match="grading_destination_or_reservation_exists"):
        preparation.prepare_observation_grading(seed.plan, **arguments)
    assert json.loads((output / preparation.READY).read_bytes()) == marker


@pytest.mark.parametrize("case", ["missing_anchor", "malformed_anchor", "wrong_R", "wrong_F", "swapped_roots",
    "same_root", "frozen_core", "runtime_helper", "observation_registration", "observation_task",
    "input_binding", "result_digest", "result_task", "result_observation", "result_input", "result_model",
    "result_pending", "result_retried", "duplicate_json", "deliverable_digest", "extra_deliverable",
    "missing_deliverable", "result_symlink", "result_hardlink", "path_traversal", "v2_step0"])
def test_time_budget_f_grading_preparation_refuses_before_publication(handoff_sources, tmp_path, case):
    seed = handoff_sources
    arguments, payload, _ = _case(seed, tmp_path)
    restore = []
    link = None
    try:
        if case == "missing_anchor":
            arguments["expected_grader_source_sha"] = None
        elif case == "malformed_anchor":
            arguments["expected_reviewed_source_sha"] = "HEAD"
        elif case in {"wrong_R", "wrong_F"}:
            arguments["expected_reviewed_source_sha" if case == "wrong_R" else "expected_grader_source_sha"] = "0" * 40
        elif case == "swapped_roots":
            arguments["runtime_root"], arguments["frozen_grader_root"] = arguments["frozen_grader_root"], arguments["runtime_root"]
        elif case == "same_root":
            arguments["frozen_grader_root"] = arguments["runtime_root"]
        elif case in {"frozen_core", "runtime_helper"}:
            path = (seed.frozen / "batch-runner/core/codex_runner.py" if case == "frozen_core"
                    else seed.runtime / preparation.HELPER)
            restore.append((path, path.read_bytes()))
            path.write_bytes(path.read_bytes() + b"\n# synthetic source drift\n")
        elif case == "observation_registration":
            arguments["observation"] = replace(arguments["observation"], registration_sha256="0" * 64)
        elif case == "observation_task":
            arguments["observation"] = replace(arguments["observation"], task_id=seed.task_ids[0])
        elif case == "input_binding":
            arguments["expected_input_binding"]["task_id"] = seed.task_ids[0]
            arguments["observation"] = replace(arguments["observation"], input_sha256=seal(arguments["expected_input_binding"]))
        elif case == "result_digest":
            arguments["expected_result_identity"]["sha256"] = "0" * 64
        elif case.startswith("result_") and case not in {"result_symlink", "result_hardlink"}:
            if case == "result_task":
                payload["results"][0]["task_id"] = seed.task_ids[0]
                payload["results"][0].update(deliverable_files=[], deliverable_file_records=[])
            elif case == "result_observation":
                payload["time_budget_observation"]["identity"]["repeat"] = 2
                payload["time_budget_observation"]["identity"]["run_id"] = "gpt54_time_budget_v1_v2_r2"
                payload["experiment_id"] = "gpt54_time_budget_v1_v2_r2"
            elif case == "result_input":
                payload["time_budget_observation"]["identity"]["input_sha256"] = "0" * 64
            elif case == "result_model":
                payload["model"] = "unregistered-model"
            elif case == "result_pending":
                payload["results"][0]["status"] = "pending"
            elif case == "result_retried":
                payload["results"][0]["retried"] = True
            _store_result(arguments, payload)  # Coherent bytes/fingerprint; independent association still refuses.
        elif case == "duplicate_json":
            data = arguments["result_path"].read_bytes().replace(b'"results":', b'"results":[],"results":', 1)
            arguments["result_path"].write_bytes(data)
            arguments["expected_result_identity"] = _identity(data)
        elif case in {"deliverable_digest", "extra_deliverable", "missing_deliverable"}:
            path = arguments["deliverables_root"] / payload["results"][0]["deliverable_files"][0]
            if case == "deliverable_digest":
                path.write_bytes(b"substituted synthetic deliverable")
            elif case == "extra_deliverable":
                path.with_name("extra.txt").write_bytes(b"undeclared")
            else:
                path.unlink()
        elif case in {"result_symlink", "result_hardlink"}:
            link = tmp_path / "result-alias.json"
            if case == "result_symlink":
                link.symlink_to(arguments["result_path"])
            else:
                os.link(arguments["result_path"], link)
            arguments["result_path"] = link
        elif case == "path_traversal":
            arguments["result_path"] = arguments["result_path"].parent / ".." / "synthetic-result" / "result.json"
        elif case == "v2_step0":
            arguments["step0_manifest"] = tmp_path / "must-not-be-read.json"
        with pytest.raises(preparation.GradingPreparationRefused):
            preparation.prepare_observation_grading(seed.plan, **arguments)
        _unpublished(arguments)
    finally:
        for path, data in restore:
            path.write_bytes(data)
        if link is not None:
            link.unlink()


@pytest.mark.parametrize("case", ["destination", "reservation"])
def test_time_budget_f_grading_preparation_no_clobber(handoff_sources, tmp_path, case):
    arguments, _, _ = _case(handoff_sources, tmp_path)
    output = arguments["destination"]
    target = output if case == "destination" else output.with_name(output.name + preparation.RESERVATION_SUFFIX)
    target.write_bytes(b"existing state must remain")
    with pytest.raises(preparation.GradingPreparationRefused, match="grading_destination_or_reservation_exists"):
        preparation.prepare_observation_grading(handoff_sources.plan, **arguments)
    assert target.read_bytes() == b"existing state must remain"


@pytest.mark.parametrize("case", ["partial_write", "result", "input", "frozen_source", "config", "copied_core", "reservation", "extra", "parent"])
def test_time_budget_f_grading_preparation_final_rereads(handoff_sources, tmp_path, monkeypatch, case):
    seed = handoff_sources
    arguments, _, _ = _case(seed, tmp_path)
    output = arguments["destination"]
    reservation = output.with_name(output.name + preparation.RESERVATION_SUFFIX)
    write = preparation._write_no_clobber
    fired, restore = [], []

    def change_after_config(path, data, *, parent_fd):
        write(path, data, parent_fd=parent_fd)
        if path != output / preparation.CONFIG or fired:
            return
        fired.append(True)
        if case == "partial_write":
            raise OSError("controlled synthetic publication interruption")
        if case == "extra":
            (output / "extra.json").write_bytes(b"{}")
        elif case == "parent":
            parent = output / "source/batch-runner"
            parent.rename(output / "source/replaced-batch-runner")
            parent.mkdir()
        else:
            target = {"result": arguments["result_path"], "input": seed.parquet,
                      "frozen_source": seed.frozen / "batch-runner/core/codex_runner.py",
                      "config": output / preparation.CONFIG,
                      "copied_core": output / "source/batch-runner/core/codex_runner.py",
                      "reservation": reservation}[case]
            restore.append((target, target.read_bytes()))
            target.write_bytes(target.read_bytes() + b"\nsynthetic changed bytes\n")

    monkeypatch.setattr(preparation, "_write_no_clobber", change_after_config)
    try:
        with pytest.raises(preparation.GradingPreparationRefused):
            preparation.prepare_observation_grading(seed.plan, **arguments)
        assert fired == [True]
        assert reservation.is_file() and output.is_dir()
        assert not (output / preparation.READY).exists()
        with pytest.raises(preparation.GradingPreparationRefused, match="grading_destination_or_reservation_exists"):
            preparation.prepare_observation_grading(seed.plan, **arguments)
        assert not (output / preparation.READY).exists()
    finally:
        for target, data in restore:
            target.write_bytes(data)
