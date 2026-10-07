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
_EXPECTED_MATERIALIZED_FILENAME_TEMPLATE = (
    "{exp_id}__{judge_slug}__{config_name}__{config_hash}__{rubric_sha}__"
    "{inference_sha}__{grader_source_hash_short}__{prompt_v}.json"
)


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


def _case(seed, tmp_path, *, condition="sandbox_v2", status="success", task_index=None):
    # Reuse the accepted preparer's genuine input/source checks to create the
    # expected identity. This is synthetic fixture setup, not a prior selector.
    if task_index is None:
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
        "execution_mode": "codex_foundry" if condition == "codex" else "agentic_sandbox_v2",
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
    assert config == {**template,
        "rubric": {**template["rubric"], "revision": seed.plan["shared"]["grading"]["rubric_revision"],
                   "cache_dir": "../data/gdpval-local"},
        "output": {**template["output"], "filename_template": _EXPECTED_MATERIALIZED_FILENAME_TEMPLATE}}
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


# The executor tests use the accepted preparation and source fixtures above.
# They do not invoke any prior selector, provider, grader or real owned child.
def _execution_case(seed, roots, tmp_path, monkeypatch, *, status="success"):
    from types import SimpleNamespace
    import gpt54_time_budget_grading_execution as execution
    from gpt54_disposable_checkout import _git

    # Raw host facts are explicitly synthetic, like the process below. Do not
    # turn this offline selector into a NAS kernel/namespace support probe or
    # mock the context hash/direction/source validators to return success.
    real_readlink = os.readlink
    namespaces = {"/proc/self/ns/" + name: f"{name}:[90000{index}]"
                  for index, name in enumerate(("pid", "mnt", "user"), 1)}

    def synthetic_namespace(path, *args, **kwargs):
        return namespaces[str(path)] if str(path) in namespaces else real_readlink(path, *args, **kwargs)

    monkeypatch.setattr(os, "readlink", synthetic_namespace)
    arguments, payload, _ = _case(seed, tmp_path, status=status, task_index=0)
    assert arguments.pop("step0_manifest") is None
    # Explicit synthetic publication-locator declarations, not a claim that a
    # result was published or that dataset/runtime SHAs are inference SHAs.
    payload.update(source_repo_id="synthetic/time-budget-results", source_revision="1" * 40)
    _store_result(arguments, payload)
    parquet = tmp_path / "isolated-synthetic-original.parquet"
    parquet.write_bytes(seed.parquet.read_bytes())
    arguments["dataset_parquet"] = parquet
    marker = preparation.prepare_observation_grading(seed.plan, **arguments)
    prepared = arguments.pop("destination")
    store = tmp_path / "attempts"
    store.mkdir(mode=0o700)
    tree = _git(roots["runtime"], "rev-parse", "--verify", roots["runtime_sha"] + "^{tree}").stdout.decode().strip()
    arguments.update(
        preparation_directory=prepared, expected_preparation_identity=_identity((prepared / preparation.READY).read_bytes()),
        expected_observation_identity=_identity(execution._encoded(asdict(arguments["observation"]))),
        expected_input_binding_identity=_identity(execution._encoded(arguments["expected_input_binding"])),
        controller_root=roots["runtime"], expected_controller_source_sha=roots["runtime_sha"],
        expected_controller_source_tree=tree, direction_file=tmp_path / "direction.json",
        expected_direction_sha256="0" * 64, expected_execution_context_sha256=execution.execution_context_sha256(),
        attempt_store=store, destination=tmp_path / "publications" / "one-execution",
    )
    clock = {"now": 1000}
    monkeypatch.setattr(execution, "time", SimpleNamespace(time=lambda: clock["now"]))
    _execution_direction(seed.plan, arguments)
    return arguments, marker, clock


def _execution_direction(plan, arguments):
    import gpt54_time_budget_grading_execution as execution

    # The fixture author declares an independent expected digest. Both here and
    # in the consumer, genuine Git/blob/input/config/result validators run.
    with execution._checked_preparation(plan, arguments) as checked:
        binding = execution._execution_binding(checked, arguments)
    document = {"direction_version": execution.DIRECTION_VERSION, "binding": binding.as_dict(),
                "not_before": 990, "expires_at": 1100}
    data = execution._encoded(document)
    arguments["direction_file"].write_bytes(data)
    arguments["expected_direction_sha256"] = _identity(data)["sha256"]
    return document


def _execution_transport(arguments, monkeypatch, *, mode="complete", after=None):
    import gpt54_time_budget_grading_execution as execution
    from core.cost_receipts import CostReceipt
    from core.grader import ItemGrade, TaskGrade

    calls = []

    def process(_self, command, *, ownership, **options):
        calls.append(tuple(command))
        key = execution._observation_key(arguments["observation"])
        claim_path = arguments["attempt_store"] / (key + ".json")
        claim = json.loads(claim_path.read_bytes())
        binding = claim["binding"]
        assert claim["state"] == "consumed_before_child_never_reusable" and claim["attempt"] == 1
        assert claim["direction_sha256"] == arguments["expected_direction_sha256"]
        assert command == binding["command"]
        batch = arguments["preparation_directory"] / "source/batch-runner"
        assert command[1] == str(batch / "step8_grade.py") and options["cwd"] == batch
        assert (batch / "step8_grade.py").read_bytes() == (arguments["frozen_grader_root"] / "batch-runner/step8_grade.py").read_bytes()
        config_path = Path(command[command.index("--config") + 1])
        assert config_path == arguments["preparation_directory"] / preparation.CONFIG
        config = json.loads(config_path.read_bytes())
        actual_hash = step8_grade.compute_grader_source_hash(config_path, config, batch_root=batch)
        assert actual_hash == binding["grader"]["materialized_source_sha256"]
        assert actual_hash != registration.FROZEN_TEMPLATE_SHA256
        assert binding["grader"]["template_source_sha256"] == registration.FROZEN_TEMPLATE_SHA256
        experiment = json.loads((arguments["preparation_directory"] / execution.EXPERIMENT).read_bytes())
        assert experiment["experiment"]["id"] == execution.FIRST_RUN
        assert experiment["data"]["filter"]["task_ids"] == [execution.FIRST_TASK]
        assert experiment["condition_a"]["model"]["deployment"] == "gpt-5.4"
        assert experiment["output"] == {"publish_to_hf": False, "submit_to_evals": False}
        assert options["timeout"] == 14520 and options["env"]["GRADER_TIME_BUDGET_SEC"] == "14400"
        assert options["env"]["HF_HUB_OFFLINE"] == options["env"]["HF_DATASETS_OFFLINE"] == "1"
        assert not {"GITHUB_TOKEN", "HF_TOKEN", "GITHUB_OUTPUT", "PYTHONPATH", "PYTHONHOME"} & options["env"].keys()
        assert options["stdout"] == options["stderr"] == subprocess.DEVNULL
        assert os.fstat(options["pass_fds"][0]).st_ino == claim_path.stat().st_ino
        owner_path, owner_binding = ownership
        assert owner_binding["cell_id"] == key and owner_binding["stage"] == "time_budget_f_grading"
        confirmed = mode != "cleanup_lost"
        owner_path.write_bytes(execution._encoded({**owner_binding,
            "phase": "reaped" if confirmed else "cleanup_unresolved",
            "tree_reaped": confirmed, "owner_reaped": confirmed}))
        if mode not in {"missing", "cancelled"}:
            loader = RubricLoader(config["rubric"]["repo_id"], config["rubric"]["revision"],
                                  str(arguments["preparation_directory"] / preparation.CACHE))
            rubric = loader.load(execution.FIRST_TASK)
            task = TaskGrade(task_id=execution.FIRST_TASK, sector=rubric.sector, occupation=rubric.occupation,
                items=[ItemGrade(rubric_item_id=item.rubric_item_id, criterion=item.criterion,
                    max_score=item.score, awarded_score=0, verdict="fail", decided_by="precheck",
                    required=None, evidence="explicit synthetic process output, no judge call",
                    precheck_pattern_id="file_exists_or_name") for item in rubric.rubric_items],
                total_awarded=0, total_max=0, pct=0, critical_fail=False, gold_referenced=False,
                judge_call_count=0, precheck_count=len(rubric.rubric_items), judge_total_latency_ms=0,
                judge_input_tokens=0, judge_output_tokens=0,
                error="synthetic_grading_failure" if mode == "error" else None,
                usage_complete=mode != "error")
            tasks = [] if mode in {"partial", "timeout"} else [step8_grade._task_to_dict(task, grading_wall_time_ms=0.0)]
            for row in tasks:
                row["grading_cost"] = CostReceipt.unavailable().as_dict()
            payload = step8_grade._build_grade_payload(exp_name=execution.FIRST_RUN,
                inf_results=json.loads((arguments["preparation_directory"] / preparation.RESULT).read_bytes()),
                config=config, config_hash=step8_grade.hash_config(str(config_path)), loader=loader,
                prompt_version=config["prompt"]["version"], task_dicts=tasks, grader_source_hash=actual_hash,
                source_inference_repo_id="synthetic/time-budget-results", source_inference_revision="1" * 40,
                azure_ai_runtime_fingerprint="f" * 64,
                azure_ai_routes=[{"workload": "grader", "runtime_fingerprint": "f" * 64,
                                  "profile": "direct-v1", "endpoint_kind": "direct-v1"}],
                run_status="partial" if mode in {"partial", "timeout"} else "diagnostic",
                expected_task_ids=[execution.FIRST_TASK], source_experiment_id=execution.FIRST_RUN,
                renderer_fingerprint={"libreoffice_binary": "synthetic-no-renderer",
                    "libreoffice_version": "synthetic-no-renderer", "pymupdf_version": "synthetic-no-renderer"})
            grade_path = Path(binding["grade_path"])
            ledger_path = grade_path.with_name(grade_path.stem + ".cost_ledger.jsonl")
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.write_bytes(b"")  # Explicit no-call synthetic ledger, not real usage.
            from core.cost_receipts import ledger_reference
            payload["cost_ledger"] = ledger_reference(ledger_path.relative_to(batch.parent), _identity(b"")["sha256"])
            if mode in {"partial", "timeout"}:
                from core.task_checkpoint import TaskProgressDraft, build_progress, write_checkpoint
                write_checkpoint(grade_path, build_progress(task_id=execution.FIRST_TASK,
                    grader_source_hash=actual_hash, rubric_item_ids=[item.rubric_item_id for item in rubric.rubric_items],
                    draft=TaskProgressDraft()))
            # Existing serializer/schema, not a fabricated successful validator.
            from core.grade_payload import validate_grade_payload
            validate_grade_payload(payload, json.loads((batch / "schemas/grade.schema.json").read_bytes()))
            step8_grade._save_json(grade_path, payload)
        if after is not None:
            after()
        if mode == "timeout":
            raise subprocess.TimeoutExpired(command, options["timeout"])
        if mode == "cancelled":
            raise KeyboardInterrupt
        return subprocess.CompletedProcess(command, 1 if mode in {"error", "partial"} else 0)

    monkeypatch.setattr(execution.owned.LocalTransport, "process", process)
    return calls


def _execution_cli(arguments, tmp_path):
    import gpt54_time_budget_grading_execution as execution

    values = dict(arguments)
    observation_path, input_path = tmp_path / "observation.json", tmp_path / "input-binding.json"
    observation_path.write_bytes(execution._encoded(asdict(values.pop("observation"))))
    input_path.write_bytes(execution._encoded(values.pop("expected_input_binding")))
    values.update(observation_file=observation_path, input_binding_file=input_path)
    for name in ("observation", "input_binding", "result", "preparation"):
        identity = values.pop("expected_" + name + "_identity")
        values[name + "_sha256"], values[name + "_size"] = identity["sha256"], identity["size"]
    for name in ("controller_source_sha", "controller_source_tree", "reviewed_source_sha", "grader_source_sha",
                 "input_source_sha", "direction_sha256", "execution_context_sha256"):
        values[name] = values.pop("expected_" + name)
    return [part for key, value in values.items() for part in ("--" + key.replace("_", "-"), str(value))]


def test_time_budget_f_grading_materialized_filename_contract(
        handoff_sources, dual_roots, tmp_path, monkeypatch, offline, record_property):
    from string import Formatter
    import gpt54_time_budget_grading_execution as execution
    from core.task_checkpoint import TaskProgressDraft, build_progress, checkpoint_path, write_checkpoint

    seed = handoff_sources
    arguments, marker, _ = _execution_case(seed, dual_roots, tmp_path, monkeypatch)
    output = arguments["preparation_directory"]
    batch = output / "source/batch-runner"
    config_path = output / preparation.CONFIG
    config = json.loads(config_path.read_bytes())
    template = load_plan(seed.frozen / GRADER)
    assert config == {**template,
        "rubric": {**template["rubric"], "revision": seed.plan["shared"]["grading"]["rubric_revision"],
                   "cache_dir": "../data/gdpval-local"},
        "output": {**template["output"], "filename_template": _EXPECTED_MATERIALIZED_FILENAME_TEMPLATE}}
    fields = ["exp_id", "judge_slug", "config_name", "config_hash", "rubric_sha",
              "inference_sha", "grader_source_hash_short", "prompt_v"]
    old_parts = list(Formatter().parse(template["output"]["filename_template"]))
    new_parts = list(Formatter().parse(config["output"]["filename_template"]))
    assert [(name, spec, conversion) for _, name, spec, conversion in old_parts if name is not None] == [
        (name, "", None) for name in fields]
    assert [(name, spec, conversion) for _, name, spec, conversion in new_parts] == [
        (name, spec, conversion) for _, name, spec, conversion in old_parts]
    assert [literal for literal, *_ in old_parts] == [
        "", "__judge_", "__", "__cfg_", "__rubric_", "__inference_", "__src_", "__", ".json"]
    assert [literal for literal, *_ in new_parts] == ["", *(["__"] * 7), ".json"]
    assert len(template["output"]["filename_template"].encode()) - len(config["output"]["filename_template"].encode()) == 31
    materialized = step8_grade.compute_grader_source_hash(config_path, config, batch_root=batch)
    assert materialized == marker["grader"]["materialized_source_sha256"] != registration.FROZEN_TEMPLATE_SHA256
    assert marker["config"] == {"path": preparation.CONFIG, **_identity(config_path.read_bytes())}

    # Observe the actual temporary checkpoint rename; delegate every file write.
    temporary_paths, measurements = [], []
    real_replace = Path.replace

    def observe_replace(path, target):
        assert path.is_file()
        temporary_paths.append(path)
        return real_replace(path, target)

    values = {"judge_slug": step8_grade._judge_slug(config["judge"]["model"]),
        "config_name": step8_grade._config_name_slug(config["config_name"]),
        "config_hash": step8_grade.hash_config(str(config_path)), "rubric_sha": config["rubric"]["revision"],
        "inference_sha": "1" * 40, "grader_source_hash_short": materialized[:16],
        "prompt_v": config["prompt"]["version"]}
    contract_batch = tmp_path / "filename-contract" / "batch-runner"
    for run in seed.plan["runs"]:
        for task_id in seed.task_ids:
            values["exp_id"] = run["run_id"]
            grade = step8_grade.resolve_grade_output_path(config, experiment_id=run["run_id"],
                judge_slug=values["judge_slug"], config_hash=values["config_hash"],
                rubric_sha=values["rubric_sha"], rubric_short_sha=values["rubric_sha"][:7],
                prompt_version=values["prompt_v"], inference_sha=values["inference_sha"],
                grader_source_hash=materialized,
                diagnostic_task_scope_sha=step8_grade._ordered_task_ids_sha256([task_id]))
            grade = (contract_batch / grade).resolve()
            assert grade.name == "__".join(values[name] for name in fields) + ".json"
            checkpoint = checkpoint_path(grade, task_id)
            assert checkpoint.name == grade.stem + "__" + task_id + ".json"
            with monkeypatch.context() as observer:
                observer.setattr(Path, "replace", observe_replace)
                assert write_checkpoint(grade, build_progress(task_id=task_id, grader_source_hash=materialized,
                    rubric_item_ids=["synthetic-item"], draft=TaskProgressDraft())) == checkpoint
            temporary = temporary_paths[-1]
            assert temporary == checkpoint.with_suffix(".json.tmp") and not temporary.exists()
            assert checkpoint.is_file()
            names = {"grade": grade, "checkpoint": checkpoint, "temporary_checkpoint": temporary,
                "ledger_sqlite": grade.with_name(grade.stem + ".cost_ledger.sqlite3"),
                "ledger_jsonl": grade.with_name(grade.stem + ".cost_ledger.jsonl")}
            sizes = {role: len(path.name.encode("utf-8")) for role, path in names.items()}
            assert all(size <= 255 for size in sizes.values()), (run["run_id"], task_id, sizes)
            measurements.append({"run_id": run["run_id"], "task_id": task_id, "basename_utf8_bytes": sizes})
    assert len(measurements) == len(temporary_paths) == 20
    assert len({(row["run_id"], row["task_id"]) for row in measurements}) == 20

    # A coherent synthetic obsolete config/marker is still not the new rule.
    # Never rewrite or adopt a historical preparation in production.
    stale = {**config, "output": template["output"]}
    stale_data = preparation._json_bytes(stale)
    config_path.write_bytes(stale_data)
    stale_hash = step8_grade.compute_grader_source_hash(config_path, stale, batch_root=batch)
    assert stale_hash != materialized
    stale_config = {"path": preparation.CONFIG, **_identity(stale_data)}
    marker["config"] = marker["grader"]["config_file"] = stale_config
    marker["grader"]["materialized_source_sha256"] = stale_hash
    marker["files"][preparation.CONFIG] = _identity(stale_data)
    reservation = output.with_name(output.name + preparation.RESERVATION_SUFFIX)
    reservation_value = json.loads(reservation.read_bytes())
    reservation_value["intent"]["config"] = stale_config
    reservation_data = preparation._json_bytes(reservation_value)
    reservation.write_bytes(reservation_data)
    marker["reservation"] = {"path": reservation.name, **_identity(reservation_data)}
    ready_data = preparation._json_bytes(marker)
    (output / preparation.READY).write_bytes(ready_data)
    arguments["expected_preparation_identity"] = _identity(ready_data)
    with pytest.raises(ValueError, match="^exact grading preparation mismatch$"):
        with execution._checked_preparation(seed.plan, arguments):
            pytest.fail("obsolete materialized filename was accepted")
    assert not arguments["destination"].exists() and list(arguments["attempt_store"].iterdir()) == []
    assert config_path.read_bytes() == stale_data and (output / preparation.READY).read_bytes() == ready_data
    assert offline == []
    record_property("materialized_filename_contract", json.dumps({
        "filename_template": config["output"]["filename_template"], "measurements": measurements,
        "config": _identity(preparation._json_bytes(config)), "materialized_source_sha256": materialized,
        "obsolete_config": _identity(stale_data), "obsolete_materialized_source_sha256": stale_hash,
        "frozen_template_sha256": registration.FROZEN_TEMPLATE_SHA256}, sort_keys=True))


@pytest.mark.parametrize("mode,terminal", [
    ("complete", "completed"), ("error", "failed"), ("partial", "failed"),
    ("timeout", "timeout"), ("cleanup_lost", "cleanup_unconfirmed"),
    ("missing", "missing_grade"), ("cancelled", "cancelled"),
])
def test_time_budget_first_f_grading_executor_roundtrip(handoff_sources, dual_roots, tmp_path, monkeypatch,
                                                     offline, capsys, mode, terminal):
    import gpt54_time_budget_grading_execution as execution

    arguments, marker, _ = _execution_case(handoff_sources, dual_roots, tmp_path, monkeypatch,
                                         status="error" if mode == "error" else "success")
    calls = _execution_transport(arguments, monkeypatch, mode=mode)
    if mode == "complete":
        assert execution.main(_execution_cli(arguments, tmp_path)) == 0
        assert json.loads(capsys.readouterr().out) == {"terminal_reason": "completed", "retry_allowed": False}
        result = json.loads((arguments["destination"] / execution.RESULT).read_bytes())
    else:
        result = execution.execute_first_observation_grading(handoff_sources.plan, **arguments)
    assert len(calls) == 1 and offline == []
    assert result["terminal_reason"] == terminal and result["retry_allowed"] is False
    assert result["cleanup_confirmed"] is (mode != "cleanup_lost")
    assert result["binding"]["result"] == marker["result"]
    assert result["binding"]["frozen_grader_source"] == marker["frozen_grader_source"]
    assert result["binding"]["once_only_scope"] == "this_independently_named_local_attempt_store_not_distributed_global"
    assert json.loads((arguments["destination"] / execution.RESULT).read_bytes()) == result
    if result["grade_file"] is not None:
        grade_data = (arguments["destination"] / "grade.json").read_bytes()
        assert _identity(grade_data) == {name: result["grade_file"][name] for name in ("sha256", "size")}
        assert grade_data == Path(result["binding"]["grade_path"]).read_bytes()
        assert json.loads(grade_data)["source_inference_experiment_id"] == execution.FIRST_RUN
        pointer = json.loads(grade_data)["cost_ledger"]
        assert (arguments["destination"] / pointer["path"]).read_bytes() == b""
        assert any(row["path"] == pointer["path"] and row["sha256"] == pointer["sha256"] for row in result["sidecar_files"])
        assert result["usage"]["complete"] is (mode not in {"error", "partial", "timeout"})
        assert result["usage"]["invoice_complete"] is False
    assert any("/_progress/" in row["path"] for row in result["sidecar_files"]) is (mode in {"partial", "timeout"})
    claim = arguments["attempt_store"] / (execution._observation_key(arguments["observation"]) + ".json")
    assert claim.is_file()
    with pytest.raises(execution.GradingExecutionRefused, match="^grading_attempt_already_claimed$"):
        execution.execute_first_observation_grading(handoff_sources.plan, **arguments)
    assert len(calls) == 1


@pytest.mark.parametrize("change", ["missing", "digest", "extra", "binding", "future", "expired", "context"])
def test_time_budget_first_f_grading_executor_direction_refusal(handoff_sources, dual_roots, tmp_path,
                                                              monkeypatch, offline, change):
    import gpt54_time_budget_grading_execution as execution

    arguments, _, clock = _execution_case(handoff_sources, dual_roots, tmp_path, monkeypatch)
    calls = _execution_transport(arguments, monkeypatch)
    path = arguments["direction_file"]
    document = json.loads(path.read_bytes())
    if change == "missing":
        path.unlink()
    elif change == "digest":
        arguments["expected_direction_sha256"] = "0" * 64
    elif change == "expired":
        clock["now"] = 1100
    elif change == "future":
        clock["now"] = 989
    else:
        if change == "extra":
            document["approved"] = True
        elif change == "binding":
            document["binding"]["controller"]["source_tree"] = "0" * 40
        else:
            document["binding"]["execution_context_sha256"] = "0" * 64
            arguments["expected_execution_context_sha256"] = "0" * 64
        data = execution._encoded(document)
        path.write_bytes(data)
        arguments["expected_direction_sha256"] = _identity(data)["sha256"]
    with pytest.raises(execution.GradingExecutionRefused):
        execution.execute_first_observation_grading(handoff_sources.plan, **arguments)
    assert calls == offline == [] and list(arguments["attempt_store"].iterdir()) == []
    assert not arguments["destination"].exists()
    assert not (arguments["preparation_directory"] / execution.EXPERIMENT).exists()


@pytest.mark.parametrize("change", ["preparation_digest", "coherent_core", "extra_member", "result", "input",
                                  "missing_inference_source", "result_fingerprint", "materialized_config",
                                  "controller", "frozen_root", "other_cell", "clobber"])
def test_time_budget_first_f_grading_executor_binding_refusal(handoff_sources, dual_roots, tmp_path,
                                                            monkeypatch, offline, change):
    import gpt54_time_budget_grading_execution as execution

    arguments, marker, _ = _execution_case(handoff_sources, dual_roots, tmp_path, monkeypatch)
    calls = _execution_transport(arguments, monkeypatch)
    prepared = arguments["preparation_directory"]
    if change == "preparation_digest":
        arguments["expected_preparation_identity"] = {**arguments["expected_preparation_identity"], "sha256": "0" * 64}
    elif change == "coherent_core":
        role = "source/batch-runner/core/codex_runner.py"
        data = (prepared / role).read_bytes() + b"\n# explicitly synthetic replacement\n"
        (prepared / role).write_bytes(data)
        marker["files"][role] = _identity(data)
        marker["grader"]["materialized_source_sha256"] = step8_grade.compute_grader_source_hash(
            prepared / preparation.CONFIG, json.loads((prepared / preparation.CONFIG).read_bytes()),
            batch_root=prepared / "source/batch-runner")
        ready = execution._encoded(marker)
        (prepared / preparation.READY).write_bytes(ready)
        arguments["expected_preparation_identity"] = _identity(ready)
    elif change == "extra_member":
        (prepared / "extra.json").write_bytes(b"{}")
    elif change == "result":
        result = json.loads(arguments["result_path"].read_bytes())
        result["results"][0]["task_id"] = handoff_sources.task_ids[1]
        _store_result(arguments, result)
    elif change == "missing_inference_source":
        result = json.loads(arguments["result_path"].read_bytes())
        result.pop("source_revision")
        _store_result(arguments, result)
    elif change == "result_fingerprint":
        result = json.loads(arguments["result_path"].read_bytes())
        result["result_fingerprint"] = "0" * 64
        data = execution._encoded(result)
        arguments["result_path"].write_bytes(data)
        arguments["expected_result_identity"] = _identity(data)
    elif change == "materialized_config":
        path = prepared / preparation.CONFIG
        config = json.loads(path.read_bytes())
        config["judge"]["generation"]["seed"] += 1
        path.write_bytes(execution._encoded(config))
    elif change == "input":
        arguments["dataset_parquet"].write_bytes(b"synthetic drift")
    elif change == "controller":
        arguments["expected_controller_source_tree"] = "0" * 40
    elif change == "frozen_root":
        arguments["frozen_grader_root"] = arguments["runtime_root"]
        arguments["expected_grader_source_sha"] = arguments["expected_reviewed_source_sha"]
    elif change == "other_cell":
        arguments["observation"] = replace(arguments["observation"], task_id=handoff_sources.task_ids[1])
        arguments["expected_observation_identity"] = _identity(execution._encoded(asdict(arguments["observation"])))
    else:
        arguments["destination"].mkdir()
    with pytest.raises(execution.GradingExecutionRefused):
        execution.execute_first_observation_grading(handoff_sources.plan, **arguments)
    assert calls == offline == [] and list(arguments["attempt_store"].iterdir()) == []
    assert not (prepared / execution.EXPERIMENT).exists()


@pytest.mark.parametrize("change", ["second_preparation", "claim_fsync", "final_input_drift",
                                  "ledger_drift", "missing_ledger"])
def test_time_budget_first_f_grading_executor_attempt_retention(handoff_sources, dual_roots, tmp_path,
                                                              monkeypatch, offline, change):
    import stat
    import gpt54_time_budget_grading_execution as execution

    arguments, _, _ = _execution_case(handoff_sources, dual_roots, tmp_path, monkeypatch)
    key = execution._observation_key(arguments["observation"])
    if change == "second_preparation":
        # A genuinely valid second preparation at another path is checked
        # BEFORE the first attempt; this negative cannot hide bad layout.
        second_arguments = {name: arguments[name] for name in (
            "observation", "expected_input_binding", "runtime_root", "expected_reviewed_source_sha",
            "frozen_grader_root", "expected_grader_source_sha", "input_registration_root",
            "expected_input_source_sha", "input_registration_path", "dataset_parquet", "reference_root",
            "result_path", "expected_result_identity", "deliverables_root")}
        other = tmp_path / "publications" / "second-preparation"
        preparation.prepare_observation_grading(handoff_sources.plan, **second_arguments, destination=other)
        second = {**arguments, "preparation_directory": other,
            "expected_preparation_identity": _identity((other / preparation.READY).read_bytes()),
            "direction_file": tmp_path / "second-direction.json", "destination": tmp_path / "publications" / "other-grade"}
        _execution_direction(handoff_sources.plan, second)
        calls = _execution_transport(arguments, monkeypatch)
        assert execution.execute_first_observation_grading(handoff_sources.plan, **arguments)["terminal_reason"] == "completed"
        with pytest.raises(execution.GradingExecutionRefused, match="^grading_attempt_already_claimed$"):
            execution.execute_first_observation_grading(handoff_sources.plan, **second)
        assert len(calls) == 1 and not second["destination"].exists()
        assert not (other / execution.EXPERIMENT).exists()
    elif change == "claim_fsync":
        original = os.fsync
        inode = arguments["attempt_store"].stat().st_ino
        events = []

        def refuse_directory_sync(fd):
            info = os.fstat(fd)
            if stat.S_ISDIR(info.st_mode) and info.st_ino == inode:
                events.append("uncertain_directory_fsync")
                raise OSError("controlled local durability failure")
            return original(fd)

        monkeypatch.setattr(os, "fsync", refuse_directory_sync)
        calls = _execution_transport(arguments, monkeypatch)
        with pytest.raises(execution.GradingExecutionRefused):
            execution.execute_first_observation_grading(handoff_sources.plan, **arguments)
        assert events == ["uncertain_directory_fsync"] and calls == []
        assert not arguments["destination"].exists()
    elif change == "final_input_drift":
        calls = _execution_transport(arguments, monkeypatch,
            after=lambda: arguments["dataset_parquet"].write_bytes(b"controlled post-child input drift"))
        with pytest.raises(execution.GradingExecutionRefused):
            execution.execute_first_observation_grading(handoff_sources.plan, **arguments)
        assert len(calls) == 1 and not (arguments["destination"] / execution.RESULT).exists()
    else:
        def alter_ledger():
            claim = json.loads((arguments["attempt_store"] / (key + ".json")).read_bytes())
            path = Path(claim["binding"]["grade_path"])
            ledger = path.with_name(path.stem + ".cost_ledger.jsonl")
            if change == "ledger_drift":
                ledger.write_bytes(b"explicit synthetic ledger drift\n")
            else:
                ledger.unlink()

        calls = _execution_transport(arguments, monkeypatch, after=alter_ledger)
        with pytest.raises(execution.GradingExecutionRefused):
            execution.execute_first_observation_grading(handoff_sources.plan, **arguments)
        assert len(calls) == 1 and not (arguments["destination"] / execution.RESULT).exists()
    claim = arguments["attempt_store"] / (key + ".json")
    before = claim.read_bytes()
    with pytest.raises(execution.GradingExecutionRefused, match="^grading_attempt_already_claimed$"):
        execution.execute_first_observation_grading(handoff_sources.plan,
            **{**arguments, "destination": tmp_path / "publications" / "never-retry"})
    assert claim.read_bytes() == before and offline == []
