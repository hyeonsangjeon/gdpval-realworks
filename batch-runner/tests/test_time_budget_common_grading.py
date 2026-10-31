"""Offline contract tests, not real captures, grades, hosted or cost evidence.

Temporary fixture repositories keep F's actual grader/rubric parsing code.
Only provider responses and host/process facts are simulated; no verdict,
grader, input validator, source check or readout is replaced with a stub.
"""

from copy import deepcopy
from dataclasses import asdict
import fcntl
import importlib
import json
import os
from pathlib import Path
import signal
import sys
import subprocess
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from core import runner_environment
from core.result_fingerprint import inference_result_fingerprint
from codex_budget_pilot_retention import _encoded
import gpt54_time_budget_common_grading as subject
import gpt54_time_budget_grading_execution as execution
import gpt54_time_budget_grading_preparation as preparation
import gpt54_time_budget_paired_readout as paired
import gpt54_time_budget_schedule as schedule
import gpt54_time_budget_serial_controller as serial
from gpt54_prepared_input_attestation import _identity
from gpt54_disposable_checkout import _git
from .test_time_budget_serial_controller import Scenario
from .test_time_budget_paired_readout import handoff_source_seed, handoff_sources, dual_roots, offline
from .test_time_budget_grading_preparation import _bind_grading_controller

RENDERER = {"libreoffice_binary": "/usr/bin/libreoffice",
            "libreoffice_version": "LibreOffice 24.2.7.2 420(Build:2)", "pymupdf_version": "1.26.3"}


@pytest.fixture
def host_facts(monkeypatch, offline, handoff_sources):
    # Raw facts, not a bypass of inspect_runtime()/require_execution(). No NAS
    # sandbox, Docker, namespace or renderer is actually launched/probed.
    # Bind the same explicit synthetic original-input declarations used by the
    # existing native intake tests; _input_contract itself is not stubbed.
    monkeypatch.setattr(execution.native_intake.native.originals, "PARQUET_PIN",
                        _identity(handoff_sources.parquet.read_bytes()))
    monkeypatch.setattr(execution.native_intake.native.originals, "STEP0_PIN",
                        _identity(handoff_sources.step0.read_bytes()))
    for key, value in {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_NAME": "offline-unit-runner", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
        "ImageOS": "ubuntu24", "ImageVersion": "20261026.354.1", "GITHUB_RUN_ID": "10001",
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "grade", "AZURE_AI_ROUTE_PROFILE": "direct-v1",
        "AZURE_OPENAI_V1_ENDPOINT": "https://unit-test.openai.azure.com/openai/v1/"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(runner_environment.platform, "freedesktop_os_release", lambda: {"ID": "ubuntu", "VERSION_ID": "24.04"})
    monkeypatch.setattr(runner_environment.platform, "system", lambda: "Linux")
    monkeypatch.setattr(runner_environment.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(subject.socket, "gethostname", lambda: "a" * 12)
    monkeypatch.setattr(subject, "get_renderer_fingerprint", lambda: dict(RENDERER))
    original_readlink = os.readlink
    namespaces = {"/proc/self/ns/" + name: f"{name}:[90000{index}]"
                  for index, name in enumerate(("pid", "mnt", "user"), 1)}
    monkeypatch.setattr(os, "readlink", lambda path, *a, **k:
                        namespaces[str(path)] if str(path) in namespaces else original_readlink(path, *a, **k))
    image = {"Id": "sha256:" + "b" * 64, "RepoDigests": [subject.GRADING_IMAGE]}
    container = {"Id": "a" * 64, "ImageID": image["Id"], "State": "running", "Image": subject.GRADING_IMAGE}

    class Daemon:
        def __init__(self, host, timeout):
            assert host == "localhost" and timeout == 10
        def request(self, method, path):
            assert method == "GET"
            url = urlsplit(path)
            assert url.path in {"/containers/json", "/images/json"}
            filters = json.loads(parse_qs(url.query)["filters"][0])
            assert filters == ({"id": ["a" * 12]} if url.path == "/containers/json"
                               else {"reference": [subject.GRADING_IMAGE]})
            self.value = container if url.path == "/containers/json" else image
        def getresponse(self):
            return SimpleNamespace(status=200, read=lambda maximum: json.dumps([self.value]).encode())
        def close(self):
            pass

    monkeypatch.setattr(subject, "_DockerConnection", Daemon)
    return container, image


def _real_f_main(command, batch, monkeypatch, calls, *, bad_response=False):
    """Use isolated F Step8 + F core imports, not current-R grader classes."""
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    original_modules = {name: module for name, module in sys.modules.items()
                        if name == "core" or name.startswith("core.") or name == "step8_grade"}
    for name in original_modules:
        sys.modules.pop(name)
    try:
        with monkeypatch.context() as local:
            local.syspath_prepend(str(batch))
            local.chdir(batch)
            local.setattr(sys, "argv", command[1:])
            frozen = importlib.import_module("step8_grade")
            grader = importlib.import_module("core.grader")
            local.setattr(frozen, "get_renderer_fingerprint", lambda: dict(RENDERER))
            assert Path(frozen.__file__) == batch / "step8_grade.py"
            assert Path(grader.__file__) == batch / "core/grader.py"
            responses = []
            observed = {}
            load_inference = frozen.load_local_inference_results
            validate_files = frozen.validate_local_deliverables

            def load():
                value = load_inference()
                observed["inference"] = deepcopy(value)
                observed["input_file"] = _identity((batch / "workspace/step2_inference_results.json").read_bytes())
                return value

            def validate(tasks, root):
                value = validate_files(tasks, root)
                observed["tasks"] = deepcopy(value)
                observed["files"] = {record["path"]: _identity((root / record["path"]).read_bytes())
                                     for task in value for record in task["deliverable_file_records"]}
                return value

            local.setattr(frozen, "load_local_inference_results", load)
            local.setattr(frozen, "validate_local_deliverables", validate)

            def create(**kwargs):
                # The actual judge constructs this request. Only its remote
                # response is fake; no serialized TaskGrade is supplied.
                responses.append(deepcopy(kwargs))
                verdict = json.dumps({"verdict": "partial", "partial_score": 0.5,
                    "evidence": "Unit-test response only.", "confidence": 1.0, "reasoning": "Offline fixture."})
                if bad_response:
                    verdict = "not a valid verdict"
                return SimpleNamespace(id="unit-response", model="gpt-5.6-sol", status="completed",
                    output=[], output_text=verdict, incomplete_details=None,
                    usage=SimpleNamespace(input_tokens=100, output_tokens=30,
                                          input_tokens_details=SimpleNamespace(cached_tokens=0)))

            client = SimpleNamespace(responses=SimpleNamespace(create=create), close=lambda: None)
            def provider_transport(workload, deployment, **options):
                assert options.pop("factory", None) is None
                routes = frozen.preflight_routes([(workload, deployment)], **options)
                return SimpleNamespace(client=client, close=lambda: None,
                                       runtime_fingerprint=routes[0]["runtime_fingerprint"])

            local.setattr(grader, "create_typed_azure_client", provider_transport)
            result = frozen.main()
            calls.append({"command": list(command), "cwd": str(batch), "responses": responses,
                          "observed": observed, "frozen_step8": str(frozen.__file__),
                          "frozen_grader": str(grader.__file__)})
            return result
    finally:
        # F normally owns a child process; its import-time signal handlers
        # must not escape this in-process unit-test transport into pytest.
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        for name in list(sys.modules):
            if name == "core" or name.startswith("core.") or name == "step8_grade":
                sys.modules.pop(name)
        sys.modules.update(original_modules)


class ContractScenario(Scenario):
    """Generate *test-only* real-schema capture bytes before binding identities.

Fixtures deliberately have no synthetic metadata in the production-schema
case; their provenance is this test, never a production migration/strip step.
Separate negatives prove real synthetic-marked captures cannot be admitted.
"""
    def __init__(self, seed, roots, root, monkeypatch):
        super().__init__(seed, root, monkeypatch)
        _bind_grading_controller(monkeypatch, roots["runtime"])
        self.grade_calls, self.contracts = [], []
        self.grading_fault = None
        (root / "grades").mkdir()
        (root / "attempts").mkdir(mode=0o700)
        tree = _git(roots["runtime"], "rev-parse", roots["runtime_sha"] + "^{tree}").stdout.decode().strip()
        self.pipeline = subject.CommonFrozenPipeline(controller_root=roots["runtime"],
            controller_source_sha=roots["runtime_sha"], controller_source_tree=tree,
            execution_root=root / "grades", attempt_store=root / "attempts", directions=self.direction)
        monkeypatch.setattr(execution.owned.LocalTransport, "process", self.process)

    def packet(self, seq):
        packet = super().packet(seq)
        bundle = self.bundles[seq]
        arguments = bundle.arguments
        payload = serial.document(arguments["result_path"])
        payload.pop("fixture_evidence_kind")
        payload.pop("source_repo_id")
        payload.pop("source_revision")
        payload["result_fingerprint"] = inference_result_fingerprint(payload)
        data = _encoded(payload)
        arguments["result_path"].write_bytes(data)
        arguments["expected_result_identity"] = _identity(data)
        manifest = serial.document(bundle.manifest)
        manifest["files"]["result/step2_inference_results.json"] = _identity(data)
        bundle.manifest.write_bytes(_encoded(manifest))
        item = self.order[seq - 1]
        record = schedule.capture_record({"plan": self.seed.plan, "cell": item.cell, "request": {"source": self.source}},
            {"claim": serial.document(bundle.claim), "returned_commit": "d" * 40}, manifest, payload)
        bundle.schedule_capture.write_bytes(_encoded(record))
        packet.update(result_identity=_identity(data), result_fingerprint=payload["result_fingerprint"])
        return packet

    def direction(self, item, binding, path):
        # Explicit test issuer, not an automatic production approval source.
        value = binding.as_dict()
        assert value["scheduled_admission"]["binding"] == item.binding(self.order)
        self.contracts.append(value)
        body = {"direction_version": execution.DIRECTION_VERSION, "binding": value,
                "not_before": 1, "expires_at": 4_000_000_000}
        path.write_bytes(execution._encoded(body))
        return _identity(path.read_bytes())["sha256"]

    def process(self, command, **kwargs):
        assert kwargs["timeout"] == execution.CHILD_SECONDS
        assert kwargs["env"]["GRADER_TIME_BUDGET_SEC"] == str(execution.STEP8_SECONDS)
        assert not any(key in kwargs["env"] for key in ("GH_TOKEN", "GITHUB_TOKEN", "HF_TOKEN"))
        # Simulate the owned-child *OS boundary*, not its grading function.
        path, binding = kwargs["ownership"]
        path.write_bytes(_encoded({**binding, "phase": "reaped", "tree_reaped": self.grading_fault != "cleanup",
                                  "owner_reaped": True}))
        if self.grading_fault == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        if self.grading_fault == "cancelled":
            raise KeyboardInterrupt("unit-test owned-child cancellation")
        if self.grading_fault == "missing":
            return SimpleNamespace(returncode=0)
        result = _real_f_main(command, kwargs["cwd"], self.monkeypatch, self.grade_calls,
                              bad_response=self.grading_fault == "judge_error")
        return SimpleNamespace(returncode=result)

    def controller(self):
        return serial.SerialController(plan=self.seed.plan, source=self.source, directory=self.root / "ledger",
            gh=serial.GhCommands(self.execute), requests=self.request, store=self.store,
            pipeline=self.pipeline, clock=lambda: self.now)


@pytest.fixture
def case(handoff_sources, dual_roots, tmp_path, monkeypatch, host_facts):
    return ContractScenario(handoff_sources, dual_roots, tmp_path / "case", monkeypatch)


def test_real_f_entrypoint_admits_one_capture(case, record_property):
    controller = case.controller()
    assert controller.run(max_steps=4) == "paused", controller.ledger.read()["stopped"]
    # Direct call also makes admission failures visible, unlike the production
    # controller's deliberately type-only external-error receipt.
    row = controller.ledger.read()["rows"][0]
    value = case.pipeline.grade(case.seed.plan, case.order[0], row["prepared"])
    state = controller.ledger.read()
    state["rows"][0].update(state="complete", grade=value)
    controller.ledger.write(state)
    assert len(case.grade_calls) == len(case.contracts) == 1
    _assert_input_contract(case, row["prepared"], case.grade_calls[0], case.contracts[0])
    readout = controller.readout()
    assert readout["observations"][0]["score_pct"] == 50, readout["observations"][0]
    assert readout["missing_pairs"] == 10
    record_property("evidence_boundary", "offline real-F entrypoint with fake provider and OS facts; no hosted/paid evidence")


def _assert_input_contract(case, prepared, called, binding):
    marker = serial.document(Path(prepared["directory"]) / preparation.READY)
    task = prepared["binding"]["cell"]["task_id"]
    batch = Path(called["cwd"])
    observed = called["observed"]
    assert [row["task_id"] for row in observed["tasks"]] == [task]
    assert observed["files"] == {row["path"]: {key: row[key] for key in ("sha256", "size")}
                                 for row in observed["tasks"][0]["deliverable_file_records"]}
    assert observed["input_file"] == binding["grading_input_origin"]["derived_result_identity"]
    config = serial.document(batch / "time-budget-grading.json")
    assert config["rubric"]["revision"] == case.seed.plan["shared"]["grading"]["rubric_revision"]
    assert config["prompt"]["version"] == "v2.2"
    assert config["judge"]["model"] == "gpt-5.6-sol" and config["judge"]["reasoning"]["effort"] == "max"
    for role, identity in marker["files"].items():
        if role != preparation.RESULT:  # Only retained-origin annotations derive new bytes.
            assert _identity((batch.parent.parent / role).read_bytes()) == identity
    original = serial.document(Path(prepared["directory"]) / preparation.RESULT)
    assert original == serial.document(Path(prepared["capture"]["arguments"]["result_path"]))
    assert "source_identity_document_sha256" not in original
    assert called["command"] == binding["command"]
    assert called["command"][-6:] == ["--tasks", task, "--limit", "1", "--source-experiment-id", marker["observation"]["run_id"]]
    assert _identity(Path(called["frozen_step8"]).read_bytes()) == marker["files"]["source/batch-runner/step8_grade.py"]
    assert _identity(Path(called["frozen_grader"]).read_bytes()) == marker["files"]["source/batch-runner/core/grader.py"]
    assert len(called["responses"]) == 1
    assert called["responses"][0]["model"] == "gpt-5.6-sol"
    assert called["responses"][0]["reasoning"]["effort"] == "max"


def _prepare(case, index=0, previous=None):
    item = case.order[index]
    case.request(item, previous)
    completion = case.packet(item.sequence)
    capture = case.pipeline.validate_capture(case.seed.plan, item, completion, case.bundles[item.sequence])
    return item, capture, case.pipeline.prepare(case.seed.plan, item, capture)


def test_native_repeat_two_uses_same_actual_F_entrypoint(case):
    item, capture, prepared = _prepare(case, 10)
    grade = case.pipeline.grade(case.seed.plan, item, prepared)
    _assert_input_contract(case, prepared, case.grade_calls[0], case.contracts[0])
    result = case.pipeline.readout(case.seed.plan, [{"capture": capture, "prepared": prepared, "grade": grade}])
    assert result["observations"][10]["score_pct"] == 50


def test_all_twenty_actual_F_entries_and_ten_non_synthetic_pairs(case, record_property):
    rows, previous = [], None
    for item in case.order:
        item, capture, prepared = _prepare(case, item.sequence - 1, previous)
        grade = case.pipeline.grade(case.seed.plan, item, prepared)
        rows.append({"capture": capture, "prepared": prepared, "grade": grade})
        previous = capture["completion"]
        _assert_input_contract(case, prepared, case.grade_calls[-1], case.contracts[-1])
    result = case.pipeline.readout(case.seed.plan, rows)
    assert (result["prepared_observations"], result["grading_executions"], result["complete_pairs"], result["missing_pairs"]) == (20, 20, 10, 0)
    assert result["evidence_kind"] == subject.EVIDENCE and "stub_grades" not in result
    assert [row["abba_position"] for row in result["observations"]] == [1] * 5 + [2] * 5 + [3] * 5 + [4] * 5
    assert all(row["score_pct"] == 50 for row in result["observations"])
    assert all(row["reported_grade"]["total_max"] == 4 for row in result["observations"])
    assert result["mean_difference_denominator"] == 10 and result["mean_score_difference_pp"] == 0
    assert len(case.grade_calls) == len(list(case.pipeline.attempt_store.iterdir())) == 20
    before = len(case.grade_calls)
    case.pipeline.recheck(case.seed.plan, rows)
    assert case.pipeline.readout(case.seed.plan, rows) == result and len(case.grade_calls) == before
    # Missing is not a fabricated zero. It removes exactly one complete pair.
    no_grade = deepcopy(rows)
    no_grade[0].pop("grade")
    missing = case.pipeline.readout(case.seed.plan, no_grade)
    assert (missing["complete_pairs"], missing["missing_pairs"]) == (9, 1)
    assert missing["observations"][0]["score_pct"] is None
    with pytest.raises(paired.PairedReadoutRefused, match="duplicate_observation"):
        case.pipeline.readout(case.seed.plan, rows[:-1] + rows[:1])
    with pytest.raises(paired.PairedReadoutRefused, match="observation_limit_exceeded"):
        case.pipeline.readout(case.seed.plan, rows + rows[:1])
    record_property("contract_counts", json.dumps({"real_F_entries": 20, "fake_provider_responses": 20,
        "actual_model_calls": 0, "input_contract_matches": 20, "pairs": 10,
        "scope": "unit fixtures only; not production observations or hosted evidence"}))


@pytest.mark.parametrize("change", ["task", "rubric", "missing_file", "changed_file", "extra_file", "synthetic"])
def test_admission_rechecks_actual_input_contract_before_judge(case, change):
    item, capture, prepared = _prepare(case)
    output = Path(prepared["directory"])
    if change == "task":
        prepared["binding"]["cell"]["task_id"] = case.order[1].task_id
    elif change == "rubric":
        config = serial.document(output / preparation.CONFIG)
        config["rubric"]["revision"] = "f" * 40
        (output / preparation.CONFIG).write_bytes(_encoded(config))
    elif change == "missing_file":
        (output / "source/batch-runner/core/grader.py").unlink()
    elif change == "changed_file":
        (output / "source/batch-runner/core/grader.py").write_bytes(b"not the pinned grader")
    elif change == "extra_file":
        (output / "unregistered.txt").write_text("not in the file inventory")
    elif change == "synthetic":
        prepared["capture"]["synthetic"] = True
    with pytest.raises((ValueError, OSError)):
        case.pipeline.grade(case.seed.plan, item, prepared)
    assert case.grade_calls == [] and list(case.pipeline.attempt_store.iterdir()) == []


def test_no_independent_direction_means_no_claim_or_model(case):
    item, _, prepared = _prepare(case)
    case.pipeline.directions = lambda *a: "0" * 64
    with pytest.raises(execution.GradingExecutionRefused):
        case.pipeline.grade(case.seed.plan, item, prepared)
    assert case.grade_calls == [] and list(case.pipeline.attempt_store.iterdir()) == []


@pytest.mark.parametrize("runtime_finished_at,admitted", [
    pytest.param(1000.999, True, id="just-before-expiry"),
    pytest.param(1002, False, id="expired-during-final-check"),
    pytest.param(1001, False, id="exact-expiry"),
])
def test_direction_window_rechecked_after_final_runtime_check(
        case, monkeypatch, record_property, runtime_finished_at, admitted):
    item, capture, prepared = _prepare(case)
    clock = {"now": 1000}
    monkeypatch.setattr(execution, "time", SimpleNamespace(time=lambda: clock["now"]))
    runtime_checks, entry_times, refusals = [], [], []
    actual_runtime = subject.require_runtime
    actual_direction = execution.require_execution_direction

    def runtime_check(handle):
        actual_runtime(handle)  # Keep the actual Docker/image/runner validator.
        runtime_checks.append(clock["now"])
        if len(runtime_checks) == 3:
            # Only the last, post-claim runtime check consumes this fake time.
            clock["now"] = runtime_finished_at

    def direction_check(binding, **kwargs):
        try:
            return actual_direction(binding, **kwargs)
        except execution.GradingExecutionRefused as error:
            refusals.append(str(error))
            raise

    def direction(item, binding, path):
        data = _encoded({"direction_version": execution.DIRECTION_VERSION,
            "binding": binding.as_dict(), "not_before": 990, "expires_at": 1001})
        path.write_bytes(data)
        return _identity(data)["sha256"]

    def owned_process(_transport, command, **kwargs):
        entry_times.append(clock["now"])
        # Existing in-process F entrypoint with fake provider, never a real child.
        return case.process(command, **kwargs)

    monkeypatch.setattr(subject, "require_runtime", runtime_check)
    monkeypatch.setattr(execution, "require_execution_direction", direction_check)
    monkeypatch.setattr(execution.owned.LocalTransport, "process", owned_process)
    case.pipeline.directions = direction
    grade = case.pipeline.grade(case.seed.plan, item, prepared)
    outcome = serial.document(Path(grade["directory"]) / execution.RESULT, grade["identity"])
    readout = case.pipeline.readout(case.seed.plan, [{"capture": capture, "prepared": prepared, "grade": grade}])
    record_property("direction_boundary", json.dumps({"expires_at": 1001,
        "runtime_finished_at": runtime_finished_at, "entry_times": entry_times,
        "refusals": refusals, "actual_model_calls": 0, "actual_owned_children": 0}))
    assert runtime_checks == [1000, 1000, 1000]
    assert entry_times == ([runtime_finished_at] if admitted else [])
    assert refusals == ([] if admitted else ["direction_admission_window_refused"])
    assert len(case.grade_calls) == int(admitted)
    assert outcome["entry_invoked"] is admitted
    assert outcome["exit_code"] == (0 if admitted else None)
    # No child means no owner/cleanup receipt; preserve the existing stop status.
    assert outcome["terminal_reason"] == ("completed" if admitted else "cleanup_unconfirmed")
    assert outcome["cleanup_confirmed"] is admitted
    assert grade["continuation_allowed"] is admitted
    assert len(list(case.pipeline.attempt_store.iterdir())) == 1
    assert outcome["retry_allowed"] is False
    assert readout["observations"][0]["score_pct"] == (50 if admitted else None)
    assert readout["mean_difference_denominator"] == 0  # No matching Codex side.
    if not admitted:
        assert outcome["grade_file"] is None and outcome["usage"]["available"] is False
        assert not (Path(grade["directory"]) / "grader-owner.json").exists()


@pytest.mark.parametrize("context_finished_at,admitted", [
    pytest.param(1000.999, True, id="just-before-expiry"),
    pytest.param(1001, False, id="exact-expiry"),
    pytest.param(1002, False, id="expired-during-context-io"),
])
def test_direction_window_checked_after_final_context_io(
        case, monkeypatch, record_property, context_finished_at, admitted):
    item, capture, prepared = _prepare(case)
    clock = {"now": 1000}
    monkeypatch.setattr(execution, "time", SimpleNamespace(time=lambda: clock["now"]))
    runtime_checks, delayed_context, entry_times, refusals = [], [], [], []
    actual_runtime = subject.require_runtime
    actual_context = execution.execution_context_sha256
    actual_direction = execution.require_execution_direction

    def runtime_check(handle):
        actual_runtime(handle)  # Keep the actual Docker/image/runner validator.
        runtime_checks.append(clock["now"])

    def context_check():
        value = actual_context()  # Preserve real identity bytes and their digest.
        if len(runtime_checks) == 3 and not delayed_context:
            # Delay only the context I/O inside the final, post-lock checker.
            clock["now"] = context_finished_at
            delayed_context.append(context_finished_at)
        return value

    def direction_check(binding, **kwargs):
        try:
            return actual_direction(binding, **kwargs)
        except execution.GradingExecutionRefused as error:
            refusals.append(str(error))
            raise

    def direction(item, binding, path):
        data = _encoded({"direction_version": execution.DIRECTION_VERSION,
            "binding": binding.as_dict(), "not_before": 990, "expires_at": 1001})
        path.write_bytes(data)
        return _identity(data)["sha256"]

    def owned_process(_transport, command, **kwargs):
        entry_times.append(clock["now"])
        # Existing in-process F entrypoint with fake provider, never a real child.
        return case.process(command, **kwargs)

    monkeypatch.setattr(subject, "require_runtime", runtime_check)
    monkeypatch.setattr(execution, "execution_context_sha256", context_check)
    monkeypatch.setattr(execution, "require_execution_direction", direction_check)
    monkeypatch.setattr(execution.owned.LocalTransport, "process", owned_process)
    case.pipeline.directions = direction
    grade = case.pipeline.grade(case.seed.plan, item, prepared)
    outcome = serial.document(Path(grade["directory"]) / execution.RESULT, grade["identity"])
    readout = case.pipeline.readout(case.seed.plan, [{"capture": capture, "prepared": prepared, "grade": grade}])
    record_property("context_io_boundary", json.dumps({"expires_at": 1001,
        "context_finished_at": context_finished_at, "entry_times": entry_times,
        "refusals": refusals, "actual_model_calls": 0, "actual_owned_children": 0}))
    assert runtime_checks == [1000, 1000, 1000] and delayed_context == [context_finished_at]
    assert entry_times == ([context_finished_at] if admitted else [])
    assert refusals == ([] if admitted else ["direction_admission_window_refused"])
    assert len(case.grade_calls) == int(admitted)
    assert outcome["entry_invoked"] is admitted
    assert outcome["exit_code"] == (0 if admitted else None)
    assert outcome["terminal_reason"] == ("completed" if admitted else "cleanup_unconfirmed")
    assert outcome["cleanup_confirmed"] is admitted
    assert grade["continuation_allowed"] is admitted
    assert outcome["retry_allowed"] is False
    assert readout["observations"][0]["score_pct"] == (50 if admitted else None)
    assert readout["mean_difference_denominator"] == 0  # No matching Codex side.
    claim = Path(outcome["claim_file"]["path"])
    before = claim.read_bytes()
    assert list(case.pipeline.attempt_store.iterdir()) == [claim]
    # A new open description can lock only if the executor released its lock.
    lock = os.open(claim, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(lock)
    if not admitted:
        assert outcome["grade_file"] is None and outcome["usage"]["available"] is False
        assert not (Path(grade["directory"]) / "grader-owner.json").exists()
        # Restore a valid instant: expiry alone must not be what prevents retry.
        clock["now"] = 1000
        with pytest.raises(ValueError):
            case.pipeline.grade(case.seed.plan, item, prepared)
        assert entry_times == [] and case.grade_calls == []
        assert claim.read_bytes() == before
        assert list(case.pipeline.attempt_store.iterdir()) == [claim]


@pytest.mark.parametrize("fault", ["timeout", "cancelled", "missing", "cleanup", "judge_error", "generation_timeout"])
def test_failed_or_interrupted_observation_is_null_never_imputed_zero(case, fault):
    if fault == "generation_timeout":
        case.fault = "clean_generation_timeout"
    else:
        case.grading_fault = fault
    item, capture, prepared = _prepare(case)
    grade = case.pipeline.grade(case.seed.plan, item, prepared)
    row = {"capture": capture, "prepared": prepared, "grade": grade}
    result = case.pipeline.readout(case.seed.plan, [row])
    assert result["complete_pairs"] == 0 and result["missing_pairs"] == 10
    assert result["mean_score_difference_pp"] is None and result["mean_difference_denominator"] == 0
    assert result["observations"][0]["score_pct"] is None
    assert result["observations"][0]["missing_reasons"]
    assert len(list(case.pipeline.attempt_store.iterdir())) == 1
    # A different caller cannot re-prepare/regrade this scheduled slot.
    before = len(case.grade_calls)
    with pytest.raises(ValueError):
        case.pipeline.grade(case.seed.plan, item, prepared)
    assert len(case.grade_calls) == before


@pytest.mark.parametrize("fault,reason", [("cleanup", "grading_cleanup_unconfirmed"), ("cancelled", "grading_cancelled")])
def test_unconfirmed_grading_cleanup_stops_controller_before_next_dispatch(case, fault, reason):
    case.grading_fault = fault
    controller = case.controller()
    assert controller.run() == "stopped"
    assert controller.ledger.read()["stopped"]["reason"] == reason
    assert len(case.dispatched) == 1
    assert len(case.grade_calls) == (1 if fault == "cleanup" else 0)
    assert controller.readout()["observations"][0]["score_pct"] is None


def test_readout_rejects_synthetic_duplicate_and_out_of_schedule_results(case):
    item, capture, prepared = _prepare(case)
    grade = case.pipeline.grade(case.seed.plan, item, prepared)
    good = {"capture": capture, "prepared": prepared, "grade": grade}
    for mode in ("prepared_synthetic", "grade_synthetic", "unknown_id", "wrong_preparation", "receipt_hash",
                 "ubuntu22", "source_sha"):
        row = deepcopy(good)
        if mode == "prepared_synthetic": row["prepared"]["fixture_evidence_kind"] = paired.EVIDENCE
        if mode == "grade_synthetic": row["grade"]["evidence_kind"] = paired.EVIDENCE
        if mode == "unknown_id": row["grade"]["observation_id"] = "0" * 64
        if mode == "wrong_preparation": row["grade"]["preparation_sha256"] = "0" * 64
        if mode == "receipt_hash": row["grade"]["identity"]["sha256"] = "0" * 64
        if mode == "ubuntu22": row["prepared"]["runner_image"]["image_os"] = "ubuntu22"
        if mode == "source_sha": row["prepared"]["capture"]["completion"]["source"]["sha"] = "0" * 40
        with pytest.raises((serial.ControllerRefused, paired.PairedReadoutRefused)):
            case.pipeline.readout(case.seed.plan, [row])
    with pytest.raises(paired.PairedReadoutRefused, match="duplicate_grade"):
        paired.aggregate_observation_pairs(case.seed.plan, [prepared], [grade, grade])
    assert len(case.grade_calls) == 1


def test_retired_handle_never_authorizes_a_new_attempt(case):
    _, capture, prepared = _prepare(case)
    with subject.prepare_scheduled_grading(case.seed.plan, capture=capture, prepared=prepared,
            **case.pipeline.controller, execution_input_directory=case.root / "grades/only.input") as handle:
        assert subject.admission_binding(handle)["capture_sha256"] == subject.seal(capture)
    with pytest.raises(serial.ControllerRefused, match="current_scheduled_intake_required"):
        subject.execute_scheduled_grading(case.seed.plan, preparation_handle=handle,
            direction_file=case.root / "missing.json", expected_direction_sha256="0" * 64,
            expected_execution_context_sha256="0" * 64, attempt_store=case.pipeline.attempt_store,
            destination=case.root / "unused")
    assert case.grade_calls == []


@pytest.mark.parametrize("marker", [{"synthetic": True}, {"fixture_evidence_kind": paired.EVIDENCE},
                                   {"metadata": {"evidence_kind": "stub_grade"}}])
def test_synthetic_markers_are_never_live(marker):
    with pytest.raises(serial.ControllerRefused, match="synthetic_evidence_forbidden"):
        subject.reject_synthetic(marker)


@pytest.mark.parametrize("fault", ["nas", "ubuntu22", "self_hosted", "image", "digest", "container"])
def test_host_and_exact_image_refused_before_any_model(host_facts, monkeypatch, fault):
    container, image = host_facts
    if fault == "nas": monkeypatch.delenv("GITHUB_ACTIONS")
    if fault == "ubuntu22": monkeypatch.setenv("ImageOS", "ubuntu22")
    if fault == "self_hosted": monkeypatch.setenv("RUNNER_ENVIRONMENT", "self-hosted")
    if fault == "image": container["Image"] = "ghcr.io/other/image:latest"
    if fault == "digest": image["RepoDigests"] = []
    if fault == "container": container["State"] = "exited"
    with pytest.raises((serial.ControllerRefused, runner_environment.ExecutionEnvironmentRefused)):
        subject.inspect_runtime()
