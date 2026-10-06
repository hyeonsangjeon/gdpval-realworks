"""Real import/reader/kernel boundary; no model, kernel adapter or host fallback.

This is a positive admission requirement, not a passing unsupported-host case.
Run its body only on the intended Linux CI host, not the known-unsupported NAS.
The fresh child reuses the retained synthetic reproduction's real validators.
"""

import ctypes
import errno
from importlib.metadata import version
import json
import os
from pathlib import Path
import signal
import sys
import time


_WAIT_ALL = 0x40000000
_FACTS_FORMAT = "gpt54-time-budget-owned-startup-facts-v1"
_RESULT_FORMAT = "gpt54-time-budget-owned-startup-result-v1"


def _kernel_facts(stage):
    """Non-reaping, self-only observations; never an admission verdict."""
    module = sys.modules.get("core.time_budget_observation_deadline")
    value = {
        "format": _FACTS_FORMAT, "stage": stage, "linux": sys.platform == "linux",
        "kernel_task_count": None, "kernel_task_comms": [],
        "task_errno": None, "comm_errno": None, "child_count": None, "child_errno": None,
        "sigchld": "default" if signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL else "nondefault",
        "alarm_idle": signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0),
        "existing_owner": getattr(getattr(module, "TimeBudgetObservation", None), "_process_owner", None) is not None,
        "waitid_echild": False, "waitid_errno": None,
        "pidfd_open": False, "pidfd_open_errno": None,
        "pidfd_signal_zero": False, "pidfd_signal_errno": None,
        "pidfd_waitid_echild": False, "pidfd_waitid_errno": None,
        "subreaper": None, "subreaper_errno": None,
        "first_failing_operation": None,
        "numpy_version": version("numpy"), "pyarrow_version": version("pyarrow"),
    }
    single_task = False
    try:
        tasks = list(Path("/proc/self/task").iterdir())
        value["kernel_task_count"] = len(tasks)
        single_task = {task.name for task in tasks} == {str(os.getpid())}
    except OSError as error:
        tasks = []
        value["task_errno"] = error.errno
    # Read comm independently: a missing children interface must not hide names.
    try:
        value["kernel_task_comms"] = sorted((task / "comm").read_text().rstrip("\n") for task in tasks)
    except OSError as error:
        value["comm_errno"] = error.errno
    if value["task_errno"] is None:
        try:
            value["child_count"] = len({pid for task in tasks for pid in (task / "children").read_text().split()})
        except OSError as error:
            value["child_errno"] = error.errno
    try:
        os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT | _WAIT_ALL)
    except OSError as error:
        value["waitid_errno"] = error.errno
        value["waitid_echild"] = error.errno == errno.ECHILD
    try:
        handle = os.pidfd_open(os.getpid())
    except (AttributeError, OSError) as error:
        value["pidfd_open_errno"] = getattr(error, "errno", None)
    else:
        value["pidfd_open"] = True
        try:
            try:
                signal.pidfd_send_signal(handle, 0)
                value["pidfd_signal_zero"] = True
            except (AttributeError, OSError) as error:
                value["pidfd_signal_errno"] = getattr(error, "errno", None)
            try:
                os.waitid(os.P_PIDFD, handle, os.WEXITED | os.WNOHANG | os.WNOWAIT | _WAIT_ALL)
            except (AttributeError, OSError) as error:
                value["pidfd_waitid_errno"] = getattr(error, "errno", None)
                value["pidfd_waitid_echild"] = isinstance(error, OSError) and error.errno == errno.ECHILD
        finally:
            os.close(handle)
    libc = ctypes.CDLL(None, use_errno=True)
    subreaper = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(subreaper), 0, 0, 0) == 0:
        value["subreaper"] = subreaper.value
    else:
        value["subreaper_errno"] = ctypes.get_errno()
    # First observed unmet prerequisite in production check order. The real
    # control below still decides; this snapshot does not explain a past run.
    checks = (
        ("supervision", value["alarm_idle"]), ("linux", value["linux"]),
        ("existing_owner", not value["existing_owner"]), ("single_kernel_task", single_task),
        ("sigchld_default", value["sigchld"] == "default"),
        ("proc_children", value["child_count"] == 0), ("waitid_echild", value["waitid_echild"]),
        ("pidfd_open", value["pidfd_open"]), ("pidfd_signal_zero", value["pidfd_signal_zero"]),
        ("pidfd_waitid_echild", value["pidfd_waitid_echild"]), ("subreaper_zero", value["subreaper"] == 0),
    )
    value["first_failing_operation"] = next((name for name, passed in checks if not passed), None)
    print(json.dumps(value, sort_keys=True), flush=True)
    return value


class _StopBeforeProvider(Exception):
    pass


def _startup_child(packet):
    report = {
        "format": _RESULT_FORMAT, "synthetic": True, "study_observation": False,
        "outcome": "failed", "operation": "before_controller_import",
        "first_failing_operation": None, "network_attempts": 0, "process_refusals": 0,
        "construction_stops": 0, "admission_entries": 0, "handoff_consumed": None,
        "admission_receipts": None, "cleanup_complete": None, "host_reusable": None,
        "generation_started": None, "result_returned": False, "diagnostics_complete": True,
    }
    controls, stages = [], set()
    consumed, store = None, None

    def facts(stage):
        if stage not in stages:
            stages.add(stage)
            return _kernel_facts(stage)

    def guard(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg", "os.system"}:
            report["network_attempts"] += 1
            raise AssertionError("external_effect_forbidden")
        if event == "subprocess.Popen":
            command = args[1]
            permitted = isinstance(command, list) and command[:2] == ["/usr/bin/git", "--no-replace-objects"]
            permitted = permitted and "-C" in command and command[command.index("-C") + 2] in {
                "config", "rev-parse", "ls-tree", "cat-file",
            }
            if not permitted:
                report["process_refusals"] += 1
                raise AssertionError("nonvalidator_process_forbidden")

    def profile(frame, event, argument):
        module, name = frame.f_globals.get("__name__"), frame.f_code.co_name
        if event == "return" and name == "<module>" and module in {"numpy", "pyarrow", "pandas", "datasets"}:
            facts("after_import_" + module)
        if (event == "return" and name == "_dataset_tasks" and module == "gpt54_prepared_input_attestation"
                and frame.f_locals.get("synchronous") is True and argument is not None):
            facts("after_synchronous_input_read")
        if module == "core.time_budget_observation_deadline":
            if event == "call" and name == "_acquire_process_ownership":
                report["operation"] = "ownership_admission"
                controls.append(frame.f_locals["self"])
                facts("ownership_admission")
            if event == "return" and name in {"_single_threaded", "_no_kernel_children"} and argument is False:
                if report["first_failing_operation"] is None:
                    report["first_failing_operation"] = name

    try:
        sys.addaudithook(guard)
        facts("before_controller_import")
        sys.setprofile(profile)
        import gpt54_time_budget_v2_ci as ci
        from contextlib import ExitStack
        from gpt54_time_budget_v2_observation import _ExecutionDirection

        facts("after_controller_import")
        registration = ci.registration
        # Only independently declared synthetic fixture identities differ.
        # All tracked-source, registration, input and direction checks are real.
        registration.ACCEPTED_BASE_SHA = packet["frozen_sha"]
        registration.ACCEPTED_BASE_TREE = packet["frozen_tree"]
        registration.SOURCE_PROFILE_SHA256 = packet["profile_sha"]
        root = Path(packet["state"])
        consumed = root / ("preparation" + registration.HANDOFF_CONSUMED_SUFFIX)
        context = {
            "roots": {"runtime_root": Path(packet["runtime"]), "frozen_root": Path(packet["frozen"]), "state_root": root},
            "plan": packet["plan"], "cell": packet["cell"],
            "request": {"source": {"sha": packet["runtime_sha"], "tree": packet["runtime_tree"]},
                        "not_before_unix": int(time.time()) - 10, "expires_unix": int(time.time()) + 1800},
            "host": ci.observation.execution_host_identity(packet["runtime_sha"]),
        }
        report["operation"] = "synthetic_preparation"
        common = ci._common(context)
        prepared = registration.prepare_observation_handoff(
            packet["plan"], **common, run_id=packet["cell"]["run_id"], task_id=packet["cell"]["task_id"],
            destination=root / "preparation", step0_manifest=None)
        report["operation"] = "controller_reconstruction"
        with ExitStack() as sources:
            marker, _, reread = ci._reconstruct(context, sources)
            assert marker == prepared
            reread()
        facts("after_controller_reconstruction")
        report["operation"] = "execution_direction"
        direction, expected = ci._direction(context, marker)
        ci._write(root / "direction.json", direction)
        checker = _ExecutionDirection(
            path=root / "direction.json", expected_sha256=ci._identity(ci._bytes(direction))["sha256"],
            expected_host_sha256=context["host"]["instance_sha256"],
            binding=registration.ObservationExecutionBinding(**direction["execution_binding"]),
            paths=direction["paths"], reviewed_source_sha=packet["runtime_sha"])
        store = root / "observation"
        store.mkdir(mode=0o700)

        def no_provider(*args, **kwargs):
            report["operation"] = "construction_stop_and_real_cleanup"
            report["construction_stops"] += 1
            raise _StopBeforeProvider

        report["operation"] = "consume_observation_handoff"
        try:
            registration.consume_observation_handoff(
                packet["plan"], **common, run_id=packet["cell"]["run_id"], task_id=packet["cell"]["task_id"],
                preparation_directory=root / "preparation", expected_preparation_identity=expected,
                observation_directory=store, require_execution_direction=checker.require_execution_direction,
                v2_backend_factory=no_provider, v2_voice_for=no_provider)
            report["result_returned"] = True
        except _StopBeforeProvider:
            # This exception comes back only after the real consumer's finally.
            report["operation"] = "verify_real_cleanup"
            assert len(controls) == 1
            record = controls[0].as_record()
            report["cleanup_complete"] = record["cleanup_complete"]
            report["host_reusable"] = record["host_reusable"]
            report["generation_started"] = controls[0].first_start is not None
            assert record["terminal_reason"] == "failed"
            assert record["cleanup_complete"] and record["host_reusable"]
            assert record["owned_processes_stopped"] and not record["cleanup_expired"]
            assert not (store / "host-lease.json").exists()
            assert type(controls[0])._process_owner is None
            assert not report["generation_started"]
            report["outcome"] = "admitted_and_cleaned_without_provider"
        report["handoff_consumed"] = consumed.is_file()
        report["admission_receipts"] = len(list(store.glob("*.admitted.json")))
        assert report["handoff_consumed"] and report["admission_receipts"] == 1
        assert report["construction_stops"] == 1 and not report["result_returned"]
        assert report["network_attempts"] == report["process_refusals"] == 0
        assert {"after_import_numpy", "after_import_pyarrow", "after_synchronous_input_read"} <= stages
        report["operation"] = "complete"
    except BaseException:
        # Never format an exception, traceback, path, provider body or type name.
        report["outcome"] = "failed"
    finally:
        sys.setprofile(None)
        report["admission_entries"] = len(controls)
        if report["first_failing_operation"] is None and report["outcome"] == "failed":
            report["first_failing_operation"] = report["operation"]
        try:
            if consumed is not None:
                report["handoff_consumed"] = consumed.is_file()
            if store is not None:
                report["admission_receipts"] = len(list(store.glob("*.admitted.json")))
            facts("after_attempt")
        except BaseException:
            report["outcome"] = "failed"
            report["diagnostics_complete"] = False
            if report["first_failing_operation"] is None:
                report["first_failing_operation"] = "final_diagnostics"
        print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if report["outcome"] == "admitted_and_cleaned_without_provider" else 2


if __name__ == "__main__":
    # Enter before importing pytest or the fixture module: those imports would
    # contaminate the child whose actual controller/library startup we measure.
    raise SystemExit(_startup_child(json.loads(Path(sys.argv[1]).read_text())))


import shutil
import subprocess

import pytest

from .test_gpt54_time_budget_comparison import dual_roots, handoff_source_seed  # noqa: F401


def _workflow_startup_environment():
    """Read the real job's static startup controls, never credentials or inputs."""
    import yaml

    root = Path(__file__).resolve().parents[2]
    observation = yaml.load(
        (root / ".github/workflows/gpt54-time-budget-first-v2.yml").read_text(),
        Loader=yaml.BaseLoader,
    )["jobs"]["observation"]
    contracts = yaml.load(
        (root / ".github/workflows/backend-tests.yml").read_text(),
        Loader=yaml.BaseLoader,
    )["jobs"]["time-budget-contracts"]
    assert observation["runs-on"] == contracts["runs-on"] == "ubuntu-22.04"
    assert observation["timeout-minutes"] == contracts["timeout-minutes"] == "45"
    expected = {
        "PYTHONDONTWRITEBYTECODE": "1", "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1", "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1",
        "JE_ARROW_MALLOC_CONF": "background_thread:false",
    }
    environment = {key: observation["env"][key] for key in expected}
    assert environment == expected
    assert "MALLOC_CONF" not in observation["env"]
    assert "ARROW_DEFAULT_MEMORY_POOL" not in observation["env"]
    return environment


def test_time_budget_owned_startup_workflow_contract():
    """This static contract does not execute the separate real-kernel body."""
    environment = _workflow_startup_environment()
    assert environment["JE_ARROW_MALLOC_CONF"] == "background_thread:false"


def test_time_budget_owned_startup(handoff_source_seed, tmp_path):
    """One fresh process, real R/F/input/direction validators and kernel control."""
    seed = handoff_source_seed
    state = tmp_path / "synthetic-state"
    state.mkdir(mode=0o700)
    (state / "inputs").mkdir(mode=0o700)
    shutil.copyfile(seed.parquet, state / "inputs/original.parquet")
    shutil.copytree(seed.references, state / "inputs/reference-only")
    packet = {name: str(getattr(seed, name)) for name in (
        "runtime", "runtime_sha", "runtime_tree", "frozen", "frozen_sha", "frozen_tree", "profile_sha")}
    packet.update(state=str(state), plan=seed.plan, cell={
        "study_id": seed.plan["study_id"], "run_id": "gpt54_time_budget_v1_v2_r1",
        "condition": "sandbox_v2", "repeat": 1, "task_id": seed.task_ids[1],
    })
    packet_path = tmp_path / "synthetic-packet.json"
    packet_path.write_text(json.dumps(packet, sort_keys=True))
    environment = {
        "PATH": str(Path(sys.executable).parent) + os.pathsep + os.defpath,
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONPATH": str(seed.runtime / "batch-runner"),
        "PYTHONNOUSERSITE": "1", **_workflow_startup_environment(),
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_NO_LAZY_FETCH": "1",
    }
    command = [sys.executable, "-u", str(Path(__file__).resolve()), str(packet_path)]
    timed_out = False
    try:
        child = subprocess.run(command, env=environment, capture_output=True, timeout=60)
        output, stderr, returncode = child.stdout, child.stderr, child.returncode
    except subprocess.TimeoutExpired as error:
        output, stderr, returncode = error.stdout or b"", error.stderr or b"", None
        timed_out = True  # subprocess.run kills/reaps only its own known child.
    diagnostics = []
    unexpected_output = False
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except (ValueError, UnicodeError):
            unexpected_output = True
            continue
        if type(value) is dict and value.get("format") in {_FACTS_FORMAT, _RESULT_FORMAT}:
            diagnostics.append(value)
        else:
            unexpected_output = True
    safe_output = json.dumps({"diagnostics": diagnostics, "timed_out": timed_out,
                              "stderr_bytes": len(stderr), "unexpected_output": unexpected_output}, sort_keys=True)
    if timed_out or returncode != 0 or stderr or unexpected_output:
        pytest.fail(safe_output, pytrace=False)
    results = [value for value in diagnostics if value["format"] == _RESULT_FORMAT]
    assert len(results) == 1, safe_output
    result = results[0]
    assert result["outcome"] == "admitted_and_cleaned_without_provider", safe_output
    assert result["diagnostics_complete"] and result["first_failing_operation"] is None, safe_output
    assert result["admission_entries"] == result["admission_receipts"] == result["construction_stops"] == 1, safe_output
    assert result["handoff_consumed"] and result["cleanup_complete"] and result["host_reusable"], safe_output
    assert not result["generation_started"] and not result["result_returned"] and not result["study_observation"], safe_output
    assert result["network_attempts"] == result["process_refusals"] == 0, safe_output
    snapshots = {value["stage"]: value for value in diagnostics if value["format"] == _FACTS_FORMAT}
    assert {"before_controller_import", "after_controller_import", "after_synchronous_input_read",
            "after_controller_reconstruction", "ownership_admission", "after_attempt"} <= snapshots.keys(), safe_output
    admitted, cleaned = snapshots["ownership_admission"], snapshots["after_attempt"]
    assert admitted["kernel_task_count"] == cleaned["kernel_task_count"] == 1, safe_output
    assert len(admitted["kernel_task_comms"]) == len(cleaned["kernel_task_comms"]) == 1, safe_output
    assert admitted["first_failing_operation"] is cleaned["first_failing_operation"] is None, safe_output
