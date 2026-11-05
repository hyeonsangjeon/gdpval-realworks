#!/usr/bin/env python3
"""Hosted-only synthetic resource/cleanup proof, never a study observation.

Real kernel ownership, real registered 1200/20 timers, real V2 backend and
Codex workspace/SDK collector. Only model I/O is scripted. Each stub writes a
file, creates an orphan, then stalls until the original generation timer fires.
No original inputs, publication, grader, provider credentials or model calls.
The CLI has no shortened deadline, endpoint, live mode or auth option.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve()
PLAN = ROOT / "batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_time_budget_v1.yaml"
PLAN_SHA256 = "e1d16d350aeb21af34104cede0d3acc0f6dc8db134338708e70168fbd9642699"
CONDITIONS = ("sandbox_v2", "codex")
FORMAT = "time-budget-resource-cleanup-v1"
PAYLOAD = b"Synthetic cleanup probe; not a benchmark answer.\n"
SAFE_ENV = (
    "GITHUB_ACTIONS", "GITHUB_EVENT_NAME", "GITHUB_REPOSITORY", "GITHUB_SHA",
    "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "RUNNER_ENVIRONMENT", "RUNNER_NAME",
    "RUNNER_OS", "RUNNER_ARCH", "RUNNER_TEMP", "ImageOS", "ImageVersion",
    "EXPECTED_SOURCE_SHA", "PROBE_WORKFLOW_SHA",
)


class ProbeRefused(ValueError):
    """Only fixed reason codes, never process output or environment contents."""


def require(value, reason):
    if not value:
        raise ProbeRefused(reason)


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def read_json(path):
    require(not path.is_symlink() and path.is_file() and path.stat().st_size <= 1024 * 1024,
            "evidence_file_unavailable")
    return json.loads(path.read_bytes())


def label():
    return {"format": FORMAT, "synthetic": True, "study_observation": False,
            "paid_execution_authorized": False, "model_calls": 0, "judge_calls": 0,
            "actual_provider_usage": None, "actual_provider_cost_usd": None}


def require_hosted():
    from core import runner_environment

    observed = runner_environment.require_execution()
    require(observed["github_hosted"] and observed["os_version_id"] == "24.04"
            and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and os.environ.get("GITHUB_REPOSITORY") == "hyeonsangjeon/gdpval-realworks",
            "hosted_ubuntu24_dispatch_required")
    return runner_environment.receipt("diagnostic", observed)


def probe_root():
    base = Path(os.environ.get("RUNNER_TEMP", ""))
    require(base.is_absolute() and base.is_dir() and base.resolve() == base,
            "runner_temp_unverified")
    root = base / "time-budget-resource-probe"
    require(not root.is_symlink(), "probe_root_symlink")
    return root


def clean_environment():
    # Read only this public allowlist. Do not copy, enumerate or inspect secrets.
    value = {name: os.environ[name] for name in SAFE_ENV if name in os.environ}
    value.update(PATH=f"{Path(sys.executable).parent}:/usr/bin:/bin:/usr/sbin:/sbin",
                 LANG="C.UTF-8", PYTHONDONTWRITEBYTECODE="1",
                 OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                 NUMEXPR_NUM_THREADS="1", JE_ARROW_MALLOC_CONF="background_thread:false",
                 HF_HUB_OFFLINE="1", HF_DATASETS_OFFLINE="1",
                 HF_HUB_DISABLE_IMPLICIT_TOKEN="1", HF_HUB_DISABLE_TELEMETRY="1",
                 GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_NO_LAZY_FETCH="1")
    return value


def command(argv, *, timeout=20):
    result = subprocess.run(argv, env=clean_environment(), stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=timeout, check=False)
    require(result.returncode == 0 and len(result.stdout) <= 64 * 1024,
            "local_inventory_command_failed")
    return result.stdout


def source_identity():
    sha = os.environ.get("EXPECTED_SOURCE_SHA", "")
    require(re.fullmatch(r"[0-9a-f]{40}", sha) is not None
            and sha == os.environ.get("GITHUB_SHA") == os.environ.get("PROBE_WORKFLOW_SHA"),
            "reviewed_source_mismatch")
    prefix = ["/usr/bin/git", "--no-replace-objects", "-C", str(ROOT)]
    require(command([*prefix, "rev-parse", "HEAD"]).strip() == sha, "checkout_source_mismatch")
    command([*prefix, "diff", "--quiet", "--no-ext-diff", "--no-textconv", sha, "--"])
    tree = command([*prefix, "rev-parse", "HEAD^{tree}"]).strip()
    require(re.fullmatch(r"[0-9a-f]{40}", tree) is not None, "checkout_tree_unverified")
    require(hashlib.sha256(PLAN.read_bytes()).hexdigest() == PLAN_SHA256, "registration_changed")
    return {"commit": sha, "tree": tree, "registration_sha256": PLAN_SHA256}


def resource_snapshot(root):
    # No Docker mutation: both registered routes are same-host, not containers.
    # A missing Docker inventory is unknown, not an empty/clean list.
    value = {**label(), "runner": require_hosted(), "recorded_unix": time.time(),
             "container_backend_used": False, "inventory_errors": []}
    commands = {
        "disk_df_bytes": ["/usr/bin/df", "-B1", "--output=source,size,used,avail,pcent,target", str(ROOT), str(root), "/tmp"],
        "memory_free_bytes": ["/usr/bin/free", "--bytes"], "cpu_count": ["/usr/bin/nproc"],
        "containers": ["/usr/bin/docker", "--config", str(root / "empty-docker-config"),
                       "--host", "unix:///var/run/docker.sock", "ps", "--all", "--quiet", "--no-trunc"],
    }
    for name, argv in commands.items():
        try:
            raw = command(argv)
            if name == "cpu_count":
                value[name] = int(raw.strip())
                require(value[name] > 0, "invalid_cpu_count")
            elif name == "containers":
                value[name] = sorted(raw.splitlines())
                require(all(re.fullmatch(r"[0-9a-f]{64}", item) for item in value[name]), "invalid_container_ids")
            else:
                require(bool(raw.strip()), "empty_resource_inventory")
                value[name] = raw
        except Exception:
            value[name] = None
            value["inventory_errors"].append(name)
    try:
        value["sandbox_preflight_temp_directories"] = sorted(
            path.name for path in root.parent.iterdir() if path.name.startswith("codex-sandbox-preflight-"))
    except OSError:
        value["sandbox_preflight_temp_directories"] = None
        value["inventory_errors"].append("sandbox_preflight_temp_directories")
    return value


def load_plan():
    import yaml
    from core import time_budget_observation_deadline as deadline

    require(hashlib.sha256(PLAN.read_bytes()).hexdigest() == PLAN_SHA256, "registration_changed")
    plan = yaml.safe_load(PLAN.read_bytes())
    budget = plan["generation_budget"]
    require(budget["seconds_per_observation"] == deadline.GENERATION_SECONDS == 1200
            and budget["local_cleanup_grace_seconds"] == deadline.CLEANUP_SECONDS == 20
            and budget["max_planned_host_lifecycle_seconds"] == 1220,
            "registered_deadline_mismatch")
    require(len(plan["source_pins"]) == 42, "registration_inventory_changed")
    return plan


def process_identity(pid):
    # Never read cmdline/environ; a dying child is absent, not a probe crash.
    try:
        text = Path(f"/proc/{pid}/stat").read_text()
    except (ProcessLookupError, FileNotFoundError):
        return None
    tail = text.rsplit(")", 1)[1].split()
    return {"pid": pid, "start_ticks": int(tail[19])}


def residue_entries(root):
    if not root.exists():
        return []
    require(root.is_dir() and not root.is_symlink(), "temporary_root_changed")
    entries = []
    for parent, directories, files in os.walk(root, followlinks=False):
        for name in sorted(directories + files):
            entries.append(str((Path(parent) / name).relative_to(root)))
            require(len(entries) <= 4096, "temporary_inventory_limit")
    return sorted(entries)


def sentinel_argv(state):
    return [sys.executable, "-I", str(SCRIPT), "sentinel", "--condition", state.name]


def audit_guard(allowed, counters):
    def guard(event, args):
        if event.startswith("socket."):
            counters["network_attempts"] += 1
            raise ProbeRefused("network_forbidden")
        if event == "subprocess.Popen" and args[0] == allowed[0] and list(args[1]) == allowed:
            return
        if event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork"}:
            counters["unexpected_process_attempts"] += 1
            raise ProbeRefused("unexpected_process_forbidden")
    return guard


def install_worker_guard(state):
    counters = {"network_attempts": 0, "unexpected_process_attempts": 0}
    sys.addaudithook(audit_guard(sentinel_argv(state), counters))
    return counters


def require_isolated():
    # Defense in depth: no live transport can escape if a fixture seam breaks.
    for kind in ("net", "pid"):
        expected = os.environ.get(f"PROBE_PARENT_{kind.upper()}NS", "")
        require(expected.isdecimal() and str(Path(f"/proc/self/ns/{kind}").stat().st_ino) != expected,
                "network_and_pid_namespace_required")


def sentinel(state):
    require_hosted()
    require_isolated()
    # The original parent exits. Its setsid child must be adopted and killed
    # by the real observation subreaper, not a process-group/name sweep.
    pid = os.fork()
    if pid:
        os._exit(0)
    os.setsid()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    pending = state / "orphan-pending.json"
    write_json(pending, process_identity(os.getpid()))
    os.link(pending, state / "orphan.json")  # visible only after a complete write
    pending.unlink()
    while True:
        signal.pause()


def spawn_orphan(state, control):
    process = subprocess.Popen(sentinel_argv(state), stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               env=dict(os.environ))  # already a public allowlist inside bwrap
    require(process.wait(timeout=5) == 0, "sentinel_parent_failed")
    end = time.monotonic() + 5
    marker = state / "orphan.json"
    while not marker.exists() and time.monotonic() < end:
        time.sleep(0.01)
    orphan = read_json(marker)
    require(orphan == process_identity(orphan["pid"]) and orphan["pid"] in control._child_pids(),
            "orphan_not_adopted")
    return orphan


def stall_until_deadline(control):
    # No fast CLI option/fake clock in the hosted path. Unit tests replace this
    # function AND kernel syscalls; their outputs are not hosted evidence.
    while True:
        time.sleep(control.remaining_seconds() + 1)
        control.check_generation()


def run_v2(state, control, plan, facts):
    import yaml
    from core.agentic_v2_conversation import AskForTool
    from core.agentic_v2_conversation_runner import TaskConversations, build_runner_factory, ceilings_from
    from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend

    template = yaml.safe_load((ROOT / plan["conditions"]["sandbox_v2"]["template"]).read_bytes())
    require(template["fixed_settings"]["per_task_timeout_seconds"] == 1200, "v2_template_budget_changed")
    backend_root = state / "temporary" / "backend"

    class Voice:
        makes_paid_calls = False

        def __init__(self):
            self.client = self  # close through the runner's original cleanup allowance

        def next_turn(self, request):
            if request.turn == 1:
                facts["synthetic_responses"] += 1
                return AskForTool("probe-write", "workspace_apply", {
                    "operation": "write", "path": "probe.txt", "content": PAYLOAD.decode(),
                }, input_tokens=1, output_tokens=1)
            require((backend_root / "work/probe.txt").read_bytes() == PAYLOAD, "synthetic_file_missing")
            facts["synthetic_artifact_sha256"] = hashlib.sha256(PAYLOAD).hexdigest()
            facts["orphan"] = spawn_orphan(state, control)
            stall_until_deadline(control)

        def close(self):
            facts["voice_closed"] = True

    conversations = TaskConversations(ceilings_from(template, SimpleNamespace(**template["cost"]["chosen_settings"])))
    factory = build_runner_factory(
        backend_factory=lambda **kw: AgenticV2FixtureBackend(root=backend_root, **kw),
        profile={"tool_contract_version": "2.0", "policy_profile_id": template.get("policy_profile_id") or "offline-full-v1",
                 "foundation_only": True},
        conversations=conversations, attempt_of=lambda _: 1, voice=Voice(),
        observation_for=lambda *_: control, budget_caps={"wall_seconds": 1200},
    )
    runner = factory(SimpleNamespace(task_id=control.identity.task_id))
    result = runner.run(task_prompt=PAYLOAD.decode(), reference_files=[], occupation="synthetic",
                        run_id=control.identity.run_id, condition_name="sandbox_v2", task_id=control.identity.task_id)
    facts["stop_reason"] = conversations.outcome_of(control.identity.task_id, 1).stop_reason.value
    # The backend removes work/ itself; only its empty fixture wrapper is ours.
    backend_root.rmdir()
    return result


@contextmanager
def native_stub(state, control, facts):
    from unittest.mock import patch
    from openai_codex import Sandbox, api
    from openai_codex._sandbox import _sandbox_policy
    from openai_codex.client import CodexClient
    from openai_codex.generated.v2_all import ThreadStartParams, TurnStartParams

    class Client(CodexClient):
        def start(self):
            self.workspace = Path(self.config.cwd)

        def notify(self, method, params=None):
            require(method == "initialized" and params is None, "unexpected_native_notification")

        def _request_raw(self, method, params=None):
            if method == "initialize":
                return {"userAgent": "synthetic-resource-probe/0.147.0",
                        "serverInfo": {"name": "synthetic", "version": "0.147.0"}}
            if method == "thread/start":
                ThreadStartParams.model_validate(params)
                require(params["model"] == "gpt-5.4" and params["approvalPolicy"] == "never"
                        and params["sandbox"] == "workspace-write", "native_settings_mismatch")
                thread = {"id": "synthetic-thread", "cliVersion": "0.147.0", "createdAt": 1, "updatedAt": 1,
                          "cwd": str(self.workspace), "ephemeral": False, "modelProvider": params["modelProvider"],
                          "preview": "synthetic", "sessionId": "synthetic-thread", "source": "exec",
                          "status": {"type": "idle"}, "turns": []}
                return {"thread": thread, "cwd": str(self.workspace), "model": params["model"],
                        "modelProvider": params["modelProvider"], "approvalPolicy": "never",
                        "approvalsReviewer": "user", "sandbox": _sandbox_policy(Sandbox.workspace_write)}
            if method == "turn/start":
                TurnStartParams.model_validate(params)
                (self.workspace / "probe.txt").write_bytes(PAYLOAD)
                facts["synthetic_artifact_sha256"] = hashlib.sha256(PAYLOAD).hexdigest()
                facts["synthetic_responses"] += 1
                facts["orphan"] = spawn_orphan(state, control)
                return {"turn": {"id": "synthetic-turn", "items": [], "status": "inProgress", "error": None}}
            require(method == "turn/interrupt", "unexpected_native_request")
            facts["native_interrupt_requested"] = True
            return {}

        def next_turn_notification(self, turn_id):
            require(turn_id == "synthetic-turn", "unexpected_native_turn")
            stall_until_deadline(control)

        def close(self):
            facts["native_client_closed"] = True
            return super().close()

    with patch.object(api, "CodexClient", Client):
        yield


def run_codex(state, control, plan, facts):
    from core.codex_runner import CodexAgentRunner
    from core.codex_runtime_config import LoopbackCodexProvider, requested_model_config_overrides

    class FixtureProvider(LoopbackCodexProvider):
        def config_overrides(self):
            return (*super().config_overrides(),
                    *requested_model_config_overrides(**plan["conditions"]["codex"]["request"]))

    # No server listens here. The fake SDK client does no socket I/O at all.
    # This separate loopback-only type cannot become a Foundry credential route.
    provider = FixtureProvider(port=1, model=plan["shared"]["model"]["deployment"])
    runner = CodexAgentRunner(provider, timeout=1200, run_id=control.identity.run_id,
                              condition_name="codex", observation_control=control)
    require(runner.preflight_auth is True, "production_auth_guard_disabled")
    with native_stub(state, control, facts):
        result = runner.run(task_prompt=PAYLOAD.decode(), model="gpt-5.4", reference_files=[],
                            run_id=control.identity.run_id, condition_name="codex", task_id=control.identity.task_id)
    facts["collected_artifact_sha256"] = [hashlib.sha256(item["content"]).hexdigest()
                                        for item in result.get("files", [])]
    return result


def evaluate_worker(record):
    from core.time_budget_observation_deadline import TIMEOUT

    control, facts = record.get("deadline", {}), record.get("fixture", {})
    fixture_ok = (facts.get("voice_closed") is True and facts.get("stop_reason") == "time_limit_reached"
                  if record.get("condition") == "sandbox_v2" else
                  record.get("condition") == "codex" and facts.get("native_client_closed") is True
                  and facts.get("native_interrupt_requested") is True
                  and facts.get("collected_artifact_sha256") == [hashlib.sha256(PAYLOAD).hexdigest()])
    return bool(fixture_ok and facts.get("synthetic_responses") == 1
        and record.get("error") is None and record.get("model_calls") == 0
        and record.get("synthetic") is True and record.get("study_observation") is False
        and record.get("observation_succeeded") is False and record.get("clock") == "real_monotonic"
        and record.get("generation_seconds") == 1200 and record.get("cleanup_seconds") == 20
        and control.get("terminal_reason") == TIMEOUT
        and 1200 <= (control.get("generation_elapsed_seconds") or 0) < 1220
        and control.get("cleanup_complete") is True and control.get("host_reusable") is True
        and control.get("owned_processes_stopped") is True and control.get("cleanup_expired") is False
        and type(control.get("cleanup_elapsed_seconds")) in (int, float)
        and 0 <= control["cleanup_elapsed_seconds"] < 20
        and type(control.get("first_start_monotonic")) in (int, float)
        and control.get("cleanup_deadline_monotonic") == control["first_start_monotonic"] + 1220
        and type(control.get("cleanup_finished_monotonic")) in (int, float)
        and control["cleanup_finished_monotonic"] < control["cleanup_deadline_monotonic"]
        and isinstance(facts.get("orphan"), dict)
        and facts.get("synthetic_artifact_sha256") == hashlib.sha256(PAYLOAD).hexdigest()
        and record.get("kernel_children_empty") is True and record.get("lease_present") is False
        and record.get("process_residues") == [] and record.get("temporary_residues") == []
        and record.get("audit") == {"network_attempts": 0, "unexpected_process_attempts": 0})


def worker(state, source):
    require_hosted()
    require_isolated()
    # Import the real runtime before exclusive single-thread/child admission.
    from core import codex_runner, agentic_v2_conversation_runner  # noqa: F401
    from core.time_budget_observation_deadline import ObservationIdentity, TimeBudgetObservation, TASK_IDS, STUDY_ID
    plan = load_plan()
    condition = state.name
    facts = {"synthetic_responses": 0}
    record = {**label(), "condition": condition, "error": None, "fixture": facts,
              "generation_seconds": 1200, "cleanup_seconds": 20, "clock": "real_monotonic",
              "container_backend_used": False, "source": source, "runner": require_hosted()}
    control = None
    record["audit"] = install_worker_guard(state)
    try:
        identity = ObservationIdentity(STUDY_ID, f"gpt54_time_budget_v1_{'v2' if condition == 'sandbox_v2' else 'codex'}_r1",
            condition, 1, TASK_IDS[0], source["commit"], source["tree"], PLAN_SHA256, hashlib.sha256(PAYLOAD).hexdigest())
        control = TimeBudgetObservation(state / "receipts", identity)
        result = (run_v2 if condition == "sandbox_v2" else run_codex)(state, control, plan, facts)
        record["observation_succeeded"] = result.get("success") is True
        record["deadline"] = control.as_record()
        # Empty wrapper directories are fixture-owned, never force-delete
        # runtime residue to turn a failed cleanup into a passing observation.
        for name in ("native", "home", "tmp"):
            (state / "temporary" / name).rmdir()
    except BaseException:
        record["error"] = "synthetic_observation_or_cleanup_failed"
        if control is not None:
            record["deadline"] = control.as_record()
    try:
        record["kernel_children_empty"] = TimeBudgetObservation._no_kernel_children()
        record["lease_present"] = (state / "receipts/host-lease.json").exists()
        orphan = facts.get("orphan")
        record["process_residues"] = (None if orphan is None else
                                      [] if process_identity(orphan["pid"]) != orphan else [orphan])
        record["temporary_residues"] = residue_entries(state / "temporary")
        record["passed"] = evaluate_worker(record)
    except Exception:
        record["passed"] = False
        record["error"] = "residue_inventory_failed"
    write_json(state / "result.json", record)
    return 0 if record["passed"] else 2


def worker_command(state, source):
    environment = clean_environment()
    environment.update(HOME=str(state / "temporary/home"), TMPDIR=str(state / "temporary/tmp"),
                       GDPVAL_CODEX_RUN_ROOT=str(state / "temporary/native"),
                       PROBE_SOURCE_TREE=source["tree"],
                       PROBE_PARENT_NETNS=str(Path("/proc/self/ns/net").stat().st_ino),
                       PROBE_PARENT_PIDNS=str(Path("/proc/self/ns/pid").stat().st_ino))
    argv = ["/usr/bin/bwrap", "--unshare-user", "--unshare-net", "--unshare-pid",
            "--die-with-parent", "--new-session", "--ro-bind", "/", "/", "--proc", "/proc",
            "--dev", "/dev", "--tmpfs", "/run", "--bind", str(state), str(state),
            "--bind", str(state / "temporary/tmp"), "/tmp", "--chdir", str(state),
            sys.executable, "-I", str(SCRIPT), "worker", "--condition", state.name]
    return argv, environment


def exercise(root):
    require_hosted()
    source = source_identity()
    load_plan()
    require(read_json(root / "artifacts/resources-before.json")["inventory_errors"] == [],
            "baseline_inventory_required")
    sandbox = read_json(root / "artifacts/sandbox-preflight.json")
    require(sandbox["status"] == "ready" and sandbox["model_calls"] == 0
            and sandbox["codex_probe_marker_verified"] is True
            and sandbox["runner_evidence"] == require_hosted(), "sandbox_proof_required")
    for condition in CONDITIONS:
        state = root / "state" / condition
        state.mkdir(mode=0o700)
        for name in ("receipts", "temporary", "temporary/home", "temporary/tmp", "temporary/native"):
            (state / name).mkdir(mode=0o700)
        argv, environment = worker_command(state, source)
        try:
            completed = subprocess.run(argv, env=environment, stdin=subprocess.DEVNULL, capture_output=True,
                                       timeout=1250, check=False)
            report = read_json(state / "result.json")
            report["worker_exit"] = completed.returncode
            report["passed"] = completed.returncode == 0 and evaluate_worker(report)
        except Exception:
            report = {**label(), "condition": condition, "passed": False,
                      "error": "isolated_worker_incomplete", "temporary_residues": residue_entries(state / "temporary")}
        write_json(root / "artifacts" / f"{condition}.json", report)
        if not report["passed"]:
            return 2  # Never start the next observation after uncertain cleanup.
    return 0


def summarize(root, before, after):
    issues, observations = [], []
    for condition in CONDITIONS:
        try:
            record = read_json(root / "artifacts" / f"{condition}.json")
            require(record["passed"] is True and record["worker_exit"] == 0 and evaluate_worker(record),
                    "worker_evidence_failed")
            require(record["runner"] == before["runner"] == after["runner"], "runner_changed")
        except Exception:
            issues.append(f"{condition}_proof_missing_or_failed")
        observations.append({"condition": condition, "temporary_residues": residue_entries(root / "state" / condition / "temporary")})
    complete = before.get("inventory_errors") == after.get("inventory_errors") == []
    added = sorted(set(after["containers"]) - set(before["containers"])) if complete else None
    temp_added = (sorted(set(after["sandbox_preflight_temp_directories"]) -
                        set(before["sandbox_preflight_temp_directories"])) if complete else None)
    if not complete:
        issues.append("resource_or_container_inventory_unavailable")
    elif added:
        issues.append("new_container_residue")
    if temp_added:
        issues.append("sandbox_preflight_temporary_residue")
    if any(item["temporary_residues"] for item in observations):
        issues.append("temporary_residue")
    return {**label(), "passed": not issues, "issues": issues, "observations": observations,
            "new_container_residues": added, "container_backend_used": False,
            "sandbox_preflight_temporary_residues": temp_added,
            "retained_intentionally": ["artifacts", "state/*/receipts", "state/*/orphan.json", "state/*/result.json"],
            "not_proven": ["actual_model_or_judge_behavior", "full_input_resource_capacity", "remote_cancellation",
                           "billing_bound", "twenty_observation_dispatch_capture_grading"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("before", "exercise", "after", "worker", "sentinel"))
    parser.add_argument("--condition", choices=CONDITIONS)
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        require_hosted()  # No process/sandbox/provider work before admission.
        root = probe_root()
        if args.stage in {"worker", "sentinel"}:
            require(args.condition in CONDITIONS, "fixture_condition_required")
            state = root / "state" / args.condition
            if args.stage == "sentinel":
                sentinel(state)
            return worker(state, {"commit": os.environ["EXPECTED_SOURCE_SHA"],
                "tree": os.environ["PROBE_SOURCE_TREE"], "registration_sha256": PLAN_SHA256})
        require(args.condition is None, "unexpected_condition")
        if args.stage == "before":
            root.mkdir(mode=0o700)
            for name in ("artifacts", "state", "empty-docker-config"):
                (root / name).mkdir(mode=0o700)
            write_json(root / "artifacts/source.json", source_identity())
            snapshot = resource_snapshot(root)
            write_json(root / "artifacts/resources-before.json", snapshot)
            return 0 if snapshot["inventory_errors"] == [] else 2
        if args.stage == "exercise":
            return exercise(root)
        after = resource_snapshot(root)
        write_json(root / "artifacts/resources-after.json", after)
        summary = summarize(root, read_json(root / "artifacts/resources-before.json"), after)
        write_json(root / "artifacts/summary.json", summary)
        return 0 if summary["passed"] else 2
    except Exception:
        # Keep a failure receipt even after missing sandbox/dependency/inventory
        # evidence. No raw exception/command/configuration/credential output.
        if 'root' in locals() and (root / "artifacts").is_dir():
            destination = root / "artifacts" / f"{args.stage}-refused.json"
            if not destination.exists():
                write_json(destination, {**label(), "passed": False, "stage": args.stage,
                                         "error": "probe_prerequisite_or_inventory_failed"})
        print("time_budget_resource_probe_refused")
        return 2


if __name__ == "__main__":
    sys.path.insert(0, str(SCRIPT.parent))
    raise SystemExit(main())
