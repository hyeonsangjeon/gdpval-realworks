"""Fixed native Actions wiring, real validators/callable, synthetic transports.

The stateful kernel fixture is local control-flow evidence, not a NAS or
Actions-host admission proof. No observation uses real credentials or inputs.
"""

import io
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit

import pytest
import yaml
from huggingface_hub import constants
from openai_codex.client import CodexClient

import gpt54_time_budget_codex_ci as ci
from core import azure_ai_clients, codex_azure_token, time_budget_observation_deadline as deadline
from core.agentic_v2_preregistration import seal
from core.result_fingerprint import validate_inference_result_fingerprint
from gpt54_prepared_input_attestation import _identity
from .test_gpt54_disposable_checkout import _FIXTURE_ENV
from .test_gpt54_time_budget_comparison import (
    dual_roots, handoff_source_seed, handoff_sources, observation_kernel,
)
from .test_time_budget_codex_observation import _expected_provider, _native_transport, _FILE, _SECRET
from .test_time_budget_first_v2_ci import PrivateStore, TOKEN

ROOT = Path(__file__).resolve().parents[2]
_REAL_RUN, _REAL_POPEN = subprocess.run, subprocess.Popen
_SINGLE_THREADED = deadline.TimeBudgetObservation._single_threaded
_CHILD_PIDS = deadline.TimeBudgetObservation._child_pids


@pytest.fixture
def local_kernel(monkeypatch, observation_kernel):
    """Reuse stateful syscall data, with the real proc-based guard methods."""
    kernel = observation_kernel
    iterdir, read_text = Path.iterdir, Path.read_text

    def tasks(path):
        if path == Path("/proc/self/task"):
            ids = [str(kernel.host)] + ([] if kernel.one_thread else ["synthetic-native-thread"])
            return iter(path / name for name in ids)
        return iterdir(path)

    def children(path, *args, **kwargs):
        if path == Path("/proc/self/task") / str(kernel.host) / "children":
            return " ".join(str(pid) for pid in kernel.child_pids())
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(deadline.TimeBudgetObservation, "_single_threaded", staticmethod(_SINGLE_THREADED))
    monkeypatch.setattr(deadline.TimeBudgetObservation, "_child_pids", staticmethod(_CHILD_PIDS))
    monkeypatch.setattr(Path, "iterdir", tasks)
    monkeypatch.setattr(Path, "read_text", children)
    return kernel


@pytest.fixture
def actions_layout(handoff_source_seed, tmp_path, monkeypatch):
    seed = handoff_source_seed
    bootstrap = tmp_path / "ordinary-bootstrap"
    with tempfile.TemporaryDirectory(prefix="time-budget-native-ci-", dir="/var/tmp") as owned:
        runner_temp = Path(owned)
        github_env = tmp_path / "github-env"
        github_env.touch(mode=0o600)
        environment = {**_FIXTURE_ENV, "GIT_ALLOW_PROTOCOL": "file", "GITHUB_WORKSPACE": str(bootstrap),
                       "RUNNER_TEMP": str(runner_temp), "REVIEWED_SOURCE_SHA": seed.runtime_sha,
                       "REVIEWED_SOURCE_TREE": seed.runtime_tree, "GITHUB_ENV": str(github_env)}
        for key in ("GDPVAL_CODEX_RUN_ROOT", "AZURE_CONFIG_DIR"):
            environment.pop(key, None)

        def local(command, *, check=True, cwd=None):
            with monkeypatch.context() as process:
                process.setattr(subprocess, "Popen", _REAL_POPEN)
                return _REAL_RUN(command, check=check, cwd=cwd, env=environment,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)

        local(["/usr/bin/git", "clone", "--shared", "--", str(seed.runtime), str(bootstrap)])
        local(["/usr/bin/git", "-C", str(bootstrap), "fetch", "--no-tags", "--", str(seed.frozen), seed.frozen_sha])
        workflow = yaml.safe_load((ROOT / ci.WORKFLOW).read_text())
        block = next(step["run"] for step in workflow["jobs"][ci.JOB]["steps"]
                     if "git worktree add --detach" in step.get("run", ""))
        # Only explicit synthetic F identities replace literals. Execute the
        # real workflow's ordinary-bootstrap/linked-source/no-clobber command.
        block = block.replace("882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2", seed.frozen_sha)
        block = block.replace("45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca", seed.frozen_tree)

        def create_sources():
            assert "GDPVAL_CODEX_RUN_ROOT" not in environment and "AZURE_CONFIG_DIR" not in environment
            # A child sees only exported values, not unexported shell variables.
            exports = '\n/bin/bash --noprofile --norc -c \'set -eu; printf "%s\\n" "$GDPVAL_CODEX_RUN_ROOT" "$AZURE_CONFIG_DIR"\''
            return local(["/bin/bash", "--noprofile", "--norc", "-c", block + exports], cwd=bootstrap, check=False)

        created = create_sources()
        assert created.returncode == 0, created.stderr.decode()
        roots = {name: runner_temp / basename for name, basename in ci.ROOT_NAMES.items()}
        propagated = {"GDPVAL_CODEX_RUN_ROOT": str(roots["native_root"]), "AZURE_CONFIG_DIR": str(roots["login_root"])}
        assert github_env.read_text() == "".join(f"{key}={value}\n" for key, value in propagated.items())
        assert created.stdout.decode().splitlines()[-2:] == list(propagated.values())
        for path in (roots["native_root"], roots["login_root"]):
            assert path.is_dir() and not path.is_symlink() and path.stat().st_mode & 0o777 == 0o700
            assert list(path.iterdir()) == []
        yield SimpleNamespace(bootstrap=bootstrap, runner_temp=runner_temp, roots=roots, workflow=workflow,
                              github_env=github_env, create_sources=create_sources,
                              git_roots={bootstrap, roots["runtime_root"], roots["frozen_root"]})


@pytest.fixture(autouse=True)
def offline(monkeypatch, handoff_sources, actions_layout, dual_roots, local_kernel):
    import huggingface_hub
    import step8_grade

    denied, auth_calls = [], []
    transport = SimpleNamespace(auth=None)

    def forbidden(*args, **kwargs):
        denied.append(True)
        pytest.fail("native controller attempted a live network/process/credential/grading effect")

    for owner, names in (
        (socket, ("create_connection", "getaddrinfo")), (socket.socket, ("connect", "connect_ex")),
        (subprocess, ("run", "Popen", "check_call", "check_output")), (os, ("system",)),
        (huggingface_hub, ("HfApi", "snapshot_download", "hf_hub_download")),
        (codex_azure_token, ("acquire_token", "get_bearer_token_provider")),
        (azure_ai_clients, ("OpenAI", "AzureOpenAI", "DefaultAzureCredential")),
        (CodexClient, ("start",)), (step8_grade.Grader, ("__init__",)),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    monkeypatch.setattr(constants, "HF_HUB_DISABLE_TELEMETRY", True)
    guard = actions_layout.workflow["jobs"][ci.JOB]["steps"][0]["run"]

    def process(command, **kwargs):
        if command[:2] == ["/usr/bin/git", "--no-replace-objects"]:
            index = command.index("-C")
            assert Path(command[index + 1]) in actions_layout.git_roots | {
                handoff_sources.runtime, handoff_sources.frozen,
                dual_roots["runtime"], dual_roots["frozen"], dual_roots["substitute"]}
            assert command[index + 2] in {"rev-parse", "config", "ls-tree", "cat-file"}
            assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == "" and kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
            assert "HF_TOKEN" not in kwargs["env"]
        elif command == ["/bin/bash", "--noprofile", "--norc", "-c", guard]:
            assert "HF_TOKEN" not in kwargs["env"] and kwargs["timeout"] == 5
        elif command == _expected_provider().auth_command():
            assert not any(os.environ.get(key) for key in ci.shared.TOKEN_KEYS)
            assert transport.auth is not None
            auth_calls.append(command)
            transport.auth(command, kwargs)
            return subprocess.CompletedProcess(command, 0, "synthetic-auth-transport-token", "")
        else:
            return forbidden()
        with monkeypatch.context() as ordinary:
            ordinary.setattr(subprocess, "Popen", _REAL_POPEN)
            return _REAL_RUN(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", process)
    for key in tuple(os.environ):
        if key.startswith(("AZURE_", "FOUNDRY_", "GITHUB_", "ACTIONS_", "HF_", "OPENAI_", "CODEX_", "RUNNER_")):
            monkeypatch.delenv(key)
    real_open, real_stat = Path.open, Path.stat

    def proc_open(path, *args, **kwargs):
        if str(path) == "/proc/sys/kernel/random/boot_id":
            return io.StringIO("00000000-1111-4222-8333-444444444444\n")
        return real_open(path, *args, **kwargs)

    def proc_stat(path, *args, **kwargs):
        if str(path) == "/proc/self/ns/pid":
            return SimpleNamespace(st_dev=55, st_ino=77)
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", proc_open)
    monkeypatch.setattr(Path, "stat", proc_stat)
    yield SimpleNamespace(transport=transport, auth_calls=auth_calls, forbidden=denied,
                          native_root=actions_layout.roots["native_root"], login=actions_layout.roots["login_root"])
    assert denied == []


@pytest.fixture
def case(handoff_sources, actions_layout, monkeypatch):
    seed, roots = handoff_sources, actions_layout.roots
    # Explicit synthetic byte pins, not successful input-validation verdicts.
    monkeypatch.setattr(ci.originals, "PARQUET_PIN", _identity(seed.parquet.read_bytes()))
    monkeypatch.setattr(ci.originals, "STEP0_PIN", _identity(seed.step0.read_bytes()))
    step0_repo = ci.registration.load_plan(seed.frozen / ci.registration.CODEX_TEMPLATE)["data"]["source"]
    step0 = {"repository_name_sha256": ci.intake.HF_STEP0_REPO_SHA256, "revision": ci.intake.HF_STEP0_REVISION,
             "member": "step0_needs_files_manifest.json", "identity": _identity(seed.step0.read_bytes())}
    request = {
        "format": ci.REQUEST_VERSION, "purpose": ci.PURPOSE, "source": {"sha": seed.runtime_sha, "tree": seed.runtime_tree},
        "frozen_source": {"sha": seed.frozen_sha, "tree": seed.frozen_tree},
        "input_registration": {"source_sha": seed.frozen_sha, "source_tree": seed.frozen_tree,
            "path": ci.registration.SOURCE_PROFILE, "sha256": seed.profile_sha},
        "cell": dict(ci.CELL), "registration_sha256": seal(seed.plan), "dataset_sha256": seal(seed.plan["shared"]["dataset"]),
        "step0": step0,
        "ci": {"repository": ci.REPOSITORY, "workflow": ci.WORKFLOW, "ref": "refs/heads/main", "actor": ci.OWNER,
               "job": ci.JOB, "attempt": 1, "run_number": 1, "runner": "ubuntu-22.04", "runner_os": "Linux", "runner_arch": "X64"},
        "paths": {"bootstrap_root": str(actions_layout.bootstrap), **{name: str(path) for name, path in roots.items()}},
        "storage": {"repository_name_sha256": ci.TARGET_SHA256, "branch": ci.BRANCH, "prefix": ci.PREFIX, "expected_parent": "1" * 40},
        "not_before_unix": int(time.time()) - 10, "expires_unix": int(time.time()) + 1800,
    }
    for key, value in {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": ci.REPOSITORY, "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": ci.OWNER, "GITHUB_TRIGGERING_ACTOR": ci.OWNER,
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_NUMBER": "1", "GITHUB_JOB": ci.JOB,
        "GITHUB_SHA": seed.runtime_sha, "TIME_BUDGET_CODEX_WORKFLOW_SHA": seed.runtime_sha,
        "GITHUB_WORKFLOW_REF": ci.REPOSITORY + "/" + ci.WORKFLOW + "@refs/heads/main",
        "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "RUNNER_ENVIRONMENT": "github-hosted", "ImageOS": "ubuntu22",
        "GITHUB_RUN_ID": "1001", "RUNNER_NAME": "synthetic-native-Actions-host",
        "GITHUB_WORKSPACE": str(actions_layout.bootstrap), "RUNNER_TEMP": str(actions_layout.runner_temp),
        "GDPVAL_CODEX_RUN_ROOT": str(roots["native_root"]), "AZURE_CONFIG_DIR": str(roots["login_root"]),
        "AZURE_AI_ROUTE_PROFILE": "direct-v1",
        "FOUNDRY_PROJECT_ENDPOINT": "https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/api/projects/gdpval-realworks",
        "HF_TOKEN": TOKEN, "JE_ARROW_MALLOC_CONF": "background_thread:false",
        "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
        "REVIEWED_SOURCE_SHA": seed.runtime_sha, "REVIEWED_SOURCE_TREE": seed.runtime_tree,
    }.items():
        monkeypatch.setenv(key, value)
    store = PrivateStore(prefix=ci.PREFIX)
    prior = ci.shared.PREFIX + "/admission.json"
    store.trees[store.head][prior] = b"Synthetic prior V2 claim; never adopted or mutated."
    store.writers[store.head][prior] = store.head
    value = SimpleNamespace(request=request, root=roots["state_root"], seed=seed, api=store,
                            downloads=[], corrupt_step0=False, prior=prior, prior_bytes=store.trees[store.head][prior])
    value.args = {"reviewed_source_sha": seed.runtime_sha, "reviewed_source_tree": seed.runtime_tree,
                  **{name: roots[name] for name in ("runtime_root", "frozen_root", "state_root", "native_root")}}
    original_bytes = {"data/train-00000-of-00001.parquet": seed.parquet.read_bytes(),
                      **{name: (seed.references / name).read_bytes() for name in seed.records},
                      step0["member"]: seed.step0.read_bytes()}

    @contextmanager
    def http(method, url, **kwargs):
        assert method == "GET" and kwargs["headers"]["authorization"] == "Bearer " + TOKEN
        assert kwargs["headers"]["Accept-Encoding"] == "identity"
        assert kwargs["max_retries"] == 0 and kwargs["follow_redirects"] is False
        assert urlsplit(url).netloc == "huggingface.co" and not os.environ.get("HF_TOKEN")
        path = unquote(urlsplit(url).path)
        prefixes = ["/datasets/openai/gdpval/resolve/" + seed.plan["shared"]["dataset"]["revision"] + "/",
                    "/datasets/" + step0_repo + "/resolve/" + step0["revision"] + "/"]
        matched = [prefix for prefix in prefixes if path.startswith(prefix)]
        assert len(matched) == 1
        member = path[len(matched[0]):]
        assert member in original_bytes and (member == step0["member"]) == (matched[0] == prefixes[1])
        value.downloads.append(member)
        data = original_bytes[member] + (b"tamper" if value.corrupt_step0 and member == step0["member"] else b"")
        yield SimpleNamespace(status_code=200, headers={"content-length": str(len(data))}, iter_raw=lambda **kw: iter((data,)))

    @contextmanager
    def client(token, deadline, **kwargs):
        assert token == TOKEN and deadline > time.monotonic()
        yield store

    monkeypatch.setattr("huggingface_hub.utils.http_stream_backoff", http)
    monkeypatch.setattr(ci.storage, "_hf_client", client)
    return value


def _arguments(case, monkeypatch):
    raw = ci._bytes(case.request).decode()
    digest = _identity(raw.encode())["sha256"]
    monkeypatch.setenv("TIME_BUDGET_CODEX_REQUEST_JSON", raw)
    monkeypatch.setenv("REQUEST_SHA256", digest)
    return {**case.args, "expected_request_sha256": digest}


def _invoke(case, monkeypatch, operation):
    arguments = _arguments(case, monkeypatch)
    return ci.main([operation, *(part for name, value in arguments.items()
                               for part in ("--" + name.replace("_", "-"), str(value)))])


def _workflow_contract(case, layout, monkeypatch):
    workflow, job = layout.workflow, layout.workflow["jobs"][ci.JOB]
    assert set(workflow.get("on", workflow.get(True))) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read", "id-token": "write"}
    assert workflow["concurrency"] == {"group": "gpt54-time-budget-first-v2-observation", "cancel-in-progress": False}
    assert job["runs-on"] == "ubuntu-22.04" and job["timeout-minutes"] == 45
    assert job["env"]["JE_ARROW_MALLOC_CONF"] == "background_thread:false"
    assert "GDPVAL_CODEX_RUN_ROOT" not in job["env"] and "AZURE_CONFIG_DIR" not in job["env"]
    env_bytes = layout.github_env.read_bytes()
    propagated = dict(line.split("=", 1) for line in env_bytes.decode().splitlines())
    assert propagated == {"GDPVAL_CODEX_RUN_ROOT": str(layout.roots["native_root"]),
                          "AZURE_CONFIG_DIR": str(layout.roots["login_root"])}
    # Discard the case fixture's values; later commands inherit only what the
    # actual bootstrap wrote to GITHUB_ENV, as a later Actions step would.
    for key in propagated:
        monkeypatch.delenv(key, raising=False)
    for key, value in propagated.items():
        monkeypatch.setenv(key, value)
    assert "HF_TOKEN" not in job["env"] and "permissions" not in job
    steps = job["steps"]
    credentialed = [step for step in steps if "HF_TOKEN" in step.get("env", {})]
    assert len(credentialed) == 2
    assert "prepare-and-claim" in credentialed[0]["run"] and "330s" in credentialed[0]["run"]
    assert " retain " in credentialed[1]["run"] and "210s" in credentialed[1]["run"]
    assert all(step["env"]["HF_TOKEN"] == "${{ secrets.HF_TOKEN }}" for step in credentialed)
    login = next(step for step in steps if step.get("uses", "").startswith("azure/login@"))
    execute = next(step for step in steps if " execute " in step.get("run", ""))
    assert steps.index(credentialed[0]) < steps.index(login) < steps.index(execute) < steps.index(credentialed[1])
    assert "HF_TOKEN" not in execute["env"] and "unset HF_TOKEN" in execute["run"]
    assert login["if"] == execute["if"] == "success() && steps.admission.outputs.acknowledged == 'true'"
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["persist-credentials"] is False and checkout["with"]["ref"] == "${{ inputs.reviewed_source_sha }}"
    arguments = _arguments(case, monkeypatch)
    source = next(step for step in steps if step.get("id") == "source")
    for step in (source, credentialed[0], login, execute):
        assert all(key not in step.get("env", {}) and os.environ[key] == value for key, value in propagated.items())
    assert list(layout.roots["login_root"].iterdir()) == []
    command = source["run"]
    argv = [os.path.expandvars(part) for part in shlex.split(command[command.index("python3 "):].replace("\\\n", ""))]
    assert argv == ["python3", str(layout.roots["runtime_root"] / ci.HELPER), "validate-request",
        "--reviewed-source-sha", arguments["reviewed_source_sha"], "--reviewed-source-tree", arguments["reviewed_source_tree"],
        "--expected-request-sha256", arguments["expected_request_sha256"], "--runtime-root", str(arguments["runtime_root"]),
        "--frozen-root", str(arguments["frozen_root"]), "--state-root", str(arguments["state_root"]),
        "--native-root", str(arguments["native_root"])]
    assert ci.main(argv[2:]) == 0
    command = ["/bin/bash", "--noprofile", "--norc", "-c", steps[0]["run"]]
    environment = {key: val for key, val in os.environ.items() if key not in ("HF_TOKEN", "FOUNDRY_PROJECT_ENDPOINT")}
    assert subprocess.run(command, env=environment, capture_output=True, timeout=5).returncode == 0
    assert subprocess.run(command, env={**environment, "GITHUB_RUN_ATTEMPT": "2"}, capture_output=True, timeout=5).returncode != 0
    assert layout.create_sources().returncode != 0
    assert layout.github_env.read_bytes() == env_bytes
    assert steps[-1]["with"] == {"name": "time-budget-first-codex-completion",
        "path": "${{ runner.temp }}/time-budget-first-codex/completion.json", "if-no-files-found": "error", "retention-days": 7}


@pytest.mark.parametrize("case_name", ["roundtrip", "failed", "source", "selection", "step0", "direction", "occupied", "uncertain"])
def test_time_budget_first_codex_ci(case, actions_layout, offline, local_kernel, monkeypatch, capsys, case_name):
    if case_name == "source":
        monkeypatch.setenv("TIME_BUDGET_CODEX_WORKFLOW_SHA", "0" * 40)
    elif case_name == "selection":
        case.request["cell"]["task_id"] = case.seed.task_ids[1]
    elif case_name == "step0":
        case.corrupt_step0 = True
    elif case_name == "occupied":
        case.api.trees[case.api.head][ci.CLAIM] = b"Synthetic consumed native claim; never adopt."
        case.api.writers[case.api.head][ci.CLAIM] = case.api.head
    if case_name in {"source", "selection"}:
        assert _invoke(case, monkeypatch, "prepare-and-claim") == 2
        assert case.downloads == case.api.calls == offline.auth_calls == []
        assert not case.root.exists()
        return
    if case_name in {"step0", "occupied"}:
        old = dict(case.api.trees[case.api.head])
        assert _invoke(case, monkeypatch, "prepare-and-claim") == 2
        assert len(case.downloads) == 4 and case.api.commits == offline.auth_calls == []
        assert case.api.trees[case.api.head] == old
        assert not (case.root / "execution-reserved.json").exists()
        assert _invoke(case, monkeypatch, "execute") == 2
        assert offline.auth_calls == []
        return
    if case_name == "roundtrip":
        _workflow_contract(case, actions_layout, monkeypatch)
    assert _invoke(case, monkeypatch, "prepare-and-claim") == 0
    assert len(case.downloads) == 4 and case.api.commits == ["claim"] and offline.auth_calls == []
    claim_bytes = case.api.trees[case.api.head][ci.CLAIM]
    claim = json.loads(claim_bytes)
    assert claim["step0_provenance"] == case.request["step0"]
    assert {key: claim["observation"][key] for key in ci.CELL} == ci.CELL
    assert ci.CLAIM != case.prior and case.api.trees[case.api.head][case.prior] == case.prior_bytes
    marker = ci._read(case.root / "preparation" / ci.registration.HANDOFF_READY)
    assert marker["inputs"]["step0_manifest"] == case.request["step0"]["identity"]
    assert (case.root / "inputs" / ci.originals.STEP0).read_bytes() == case.seed.step0.read_bytes()
    # Simulate a later approved-login step without reading or making credentials.
    (offline.login / "synthetic-session").write_bytes(b"Synthetic login state, not an authorization or credential.")
    if case_name == "direction":
        direction = case.root / "direction.json"
        direction.write_bytes(direction.read_bytes() + b" ")
        assert _invoke(case, monkeypatch, "execute") == 2
        assert offline.auth_calls == [] and not (case.root / "execution-reserved.json").exists()
        assert case.api.commits == ["claim"] and case.api.trees[case.api.head][ci.CLAIM] == claim_bytes
        return
    spec = SimpleNamespace(arguments={"observation": deadline.ObservationIdentity(**marker["observation"])},
                           marker=marker, consumed=case.root / ("preparation" + ci.registration.HANDOFF_CONSUMED_SUFFIX))
    native = _native_transport(monkeypatch, spec, offline, outcome="failed" if case_name == "failed" else "success")
    if case_name == "uncertain":
        local_kernel.one_thread = False
    assert _invoke(case, monkeypatch, "execute") == (2 if case_name == "uncertain" else 1 if case_name == "failed" else 0)
    assert not any(os.environ.get(key) for key in ci.shared.TOKEN_KEYS)
    assert spec.consumed.is_file() and (case.root / "execution-reserved.json").is_file()
    result_path = case.root / "result" / ci.observation.RESULT
    if case_name == "uncertain":
        assert not result_path.exists() and native.requests == offline.auth_calls == []
        receipt = ci._read(case.root / "execution-receipt.json")
        assert receipt["returned"] is None and receipt["failure"]["stage"] == "observation_callable"
        assert receipt["failure"]["reason"] == deadline.OWNERSHIP_REQUIRED
    else:
        data = result_path.read_bytes()
        payload = json.loads(data)
        assert payload["condition"] == "codex" and payload["execution_mode"] == "codex_foundry"
        assert payload["results"][0]["task_id"] == ci.CELL["task_id"]
        assert payload["results"][0]["usage"] is None
        assert all(value is None for value in payload["results"][0]["observability"]["native_measurements"].values())
        assert payload["time_budget_observation"] == native.controls[0].as_record()
        assert native.controls[0].cleanup_complete and native.controls[0].as_record()["host_reusable"]
        assert native.controls[0].cleanup_deadline - native.controls[0].terminal_at == 20
        assert [method for method, _ in native.requests] == ["initialize", "thread/start", "turn/start"]
        assert len(native.controls) == len(offline.auth_calls) == len(native.clients) == 1
    attempts = list(native.requests)
    assert _invoke(case, monkeypatch, "execute") == 2 and native.requests == attempts
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    assert _invoke(case, monkeypatch, "retain") == 0
    envelope = ci._read(case.root / "completion.json")
    ci.validate_envelope(envelope)
    assert _invoke(case, monkeypatch, "verify-envelope") == 0
    assert {key: envelope[key] for key in ci.CELL} == ci.CELL
    assert envelope["retention"] == "acknowledged" and envelope["usage"] is None
    assert envelope["retry_allowed"] is False and envelope["grading_performed"] is False and envelope["other_cells_executed"] == 0
    assert case.api.commits == ["claim", "output"] and case.api.trees[case.api.head][ci.CLAIM] == claim_bytes
    assert case.api.trees[case.api.head][case.prior] == case.prior_bytes
    private = json.loads(case.api.trees[case.api.head][ci.MANIFEST])
    if case_name == "uncertain":
        assert envelope["status"] == "uncertain" and private["result"] == "unavailable_no_fabricated_study_row"
        assert private["execution_receipt"] == receipt and private["files"] == {}
        assert all(envelope[key] is None for key in (
            "result_identity", "result_fingerprint", "terminal_reason", "cleanup_complete", "host_reusable"))
    else:
        assert envelope["status"] == ("error" if case_name == "failed" else "success")
        assert envelope["result_identity"] == _identity(data)
        assert envelope["result_fingerprint"] == validate_inference_result_fingerprint(payload)
        assert case.api.trees[case.api.head][ci.PREFIX + "/result/" + ci.observation.RESULT] == data
        member = f"result/upload/deliverable_files/{ci.CELL['task_id']}/deliverable.txt"
        assert case.api.trees[case.api.head][ci.PREFIX + "/" + member] == _FILE
        assert private["files"][member] == _identity(_FILE)
    captured = capsys.readouterr()
    public = captured.out + captured.err + (case.root / "completion.json").read_text()
    assert all(secret not in public for secret in (TOKEN, _SECRET, "Synthetic final answer.", "deliverable.txt", "reference_files"))
    with pytest.raises(ValueError):
        ci.validate_envelope({**envelope, "raw_exception": _SECRET})


@pytest.mark.parametrize("mode", [
    "fresh_secret", "pre_reservation", "old_state", "reservation_io", "receipt_io", "receipt_ack_io",
    "missing_metadata", "malformed_metadata", "invalid_protocol", "stderr_io", "v2_compatibility",
])
def test_time_budget_native_failure_event(case, offline, monkeypatch, capsys, mode):
    """Current synthetic failure only; no native process or kernel admission."""
    shared = ci.shared
    secret = "synthetic-token Authorization: Bearer hidden /private/input.json provider-body"
    base = {"outcome": "refused_or_uncertain", "returned": None}
    failure = {"stage": "observation_callable", "category": "type_error",
               "reason": "execution_refused_or_uncertain"}
    receipt = {**base, "failure": failure}
    native_format = "gpt54-time-budget-first-codex-ci-failure-v1"
    line = ('{"category":"type_error","format":"gpt54-time-budget-first-codex-ci-failure-v1",'
            '"reason":"execution_refused_or_uncertain","stage":"observation_callable"}\n')
    if mode in {"missing_metadata", "malformed_metadata", "invalid_protocol", "v2_compatibility"}:
        before = ci._bytes(receipt)
        if mode == "missing_metadata":
            shared._emit_execution_failure(base, format_version=native_format)
            with pytest.raises(TypeError):
                shared._emit_execution_failure(None, format_version=native_format)
        elif mode == "malformed_metadata":
            invalid = [{**failure, key: secret} for key in failure]
            invalid += [None, {**failure, "detail": secret}, {**failure, "reason": [failure["reason"]]}]
            for value in invalid:
                with pytest.raises(shared.FirstV2CIRefused) as refused:
                    shared._emit_execution_failure({**base, "failure": value}, format_version=native_format)
                assert refused.value.args == ("execution_failure_schema",)
            with pytest.raises(shared.FirstV2CIRefused) as refused:
                shared._emit_execution_failure({**receipt, "private": secret}, format_version=native_format)
            assert refused.value.args == ("execution_receipt_schema",)
        elif mode == "invalid_protocol":
            for value in (secret, "", None, {}, [native_format]):
                with pytest.raises(shared.FirstV2CIRefused) as refused:
                    shared._emit_execution_failure(receipt, format_version=value)
                assert refused.value.args == ("execution_failure_schema",)
        else:
            shared._emit_execution_failure(receipt)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == (line.replace("first-codex-ci", "first-v2-ci") if mode == "v2_compatibility" else "")
        assert ci._bytes(receipt) == before
        assert case.downloads == case.api.calls == case.api.commits == offline.auth_calls == []
        assert not case.root.exists()
        return

    formatted, admissions, read_failures, writes, emissions = [], [], [], [], []

    class SecretReadError(TypeError):
        def __str__(self):
            formatted.append(True)
            pytest.fail("secret exception text must never be formatted")

    class SecretIOError(OSError):
        def __str__(self):
            formatted.append(True)
            pytest.fail("secret I/O exception text must never be formatted")

    def no_admission(*args, **kwargs):
        admissions.append(True)
        pytest.fail("diagnostic selector must stop before kernel/native admission")

    monkeypatch.setattr(deadline.TimeBudgetObservation, "__init__", no_admission)
    previous_mask, previous_logging = os.umask(0o077), ci.logging.root.manager.disable
    try:
        assert _invoke(case, monkeypatch, "prepare-and-claim") == 0
        assert len(case.downloads) == 4 and case.api.commits == ["claim"]
        prepared = capsys.readouterr()
        assert prepared.out == '{"operation":"prepare-and-claim","outcome":"completed"}\n' and prepared.err == ""
        reservation, receipt_path = case.root / "execution-reserved.json", case.root / "execution-receipt.json"
        direction = case.root / "direction.json"
        expected_receipt = ci._bytes(receipt)
        if mode == "pre_reservation":
            direction.write_bytes(direction.read_bytes() + b" ")
            expected_receipt = None
        elif mode == "old_state":
            claim = ci._read(case.root / "claim-receipt.json")
            ci._write(reservation, {"claim_commit": claim["returned_commit"],
                "observation": claim["claim"]["observation"], "outcome": "uncertain_until_returned"})
            old = {**base, "failure": {**failure, "stage": "execution_source_reread", "category": "io_error"}}
            shared._check_execution_failure(old)
            ci._write(receipt_path, old)
            expected_receipt = ci._bytes(old)
        elif mode in {"reservation_io", "receipt_io"}:
            expected_receipt = None
        protected = {path: path.read_bytes() for path in (
            case.root / "claim-reserved.json", case.root / "claim-receipt.json", direction,
            case.root / "preparation" / ci.registration.HANDOFF_READY)}
        private_tree = dict(case.api.trees[case.api.head])
        calls, downloads = list(case.api.calls), list(case.downloads)
        real_open, real_write, real_read = os.open, shared._write_no_clobber, ci._read
        armed = mode in {"fresh_secret", "receipt_io", "receipt_ack_io", "stderr_io"}

        def open_file(path, *args, **kwargs):
            nonlocal armed
            if armed and isinstance(path, (str, os.PathLike)) and Path(path) == direction and reservation.exists():
                armed = False
                read_failures.append("direction_open_after_reservation")
                assert not any(os.environ.get(key) for key in shared.TOKEN_KEYS)
                raise SecretReadError(secret)
            return real_open(path, *args, **kwargs)

        def write(path, data, **kwargs):
            if path in {reservation, receipt_path}:
                writes.append(path.name)
                if mode == "receipt_io" and path == receipt_path:
                    raise SecretIOError(secret)
                real_write(path, data, **kwargs)
                if (mode == "reservation_io" and path == reservation
                        or mode == "receipt_ack_io" and path == receipt_path):
                    raise SecretIOError(secret)  # Persisted bytes do not imply an acknowledged write.
                return
            return real_write(path, data, **kwargs)

        def read(path):
            assert path != receipt_path, "execution must never read an old receipt to emit a diagnostic"
            return real_read(path)

        stderr = shared.sys.stderr

        def emit(text):
            emissions.append(text)
            assert reservation.is_file() and receipt_path.read_bytes() == ci._bytes(receipt)
            assert writes == [reservation.name, receipt_path.name]
            assert json.loads(text) == {"format": native_format, **failure}
            if mode == "stderr_io":
                raise SecretIOError(secret)
            return stderr.write(text)

        monkeypatch.delenv("HF_TOKEN", raising=False)
        with monkeypatch.context() as executing:
            executing.setattr(os, "open", open_file)
            executing.setattr(shared, "_write_no_clobber", write)
            executing.setattr(ci, "_read", read)
            executing.setattr(shared.sys, "stderr", SimpleNamespace(write=emit))
            assert _invoke(case, monkeypatch, "execute") == 2
            captured = capsys.readouterr()
            assert captured.out == '{"outcome":"refused_or_uncertain"}\n'
            assert captured.err == (line if mode == "fresh_secret" else "")
            assert emissions == ([line] if mode in {"fresh_secret", "stderr_io"} else [])
            reserved_bytes = reservation.read_bytes() if reservation.exists() else None
            assert (receipt_path.read_bytes() if receipt_path.exists() else None) == expected_receipt
            assert (reserved_bytes is None) == (mode == "pre_reservation")
            assert {path: path.read_bytes() for path in protected} == protected
            assert case.api.trees[case.api.head] == private_tree
            # A duplicate synthetic invocation must not format or emit a retained failure.
            assert _invoke(case, monkeypatch, "execute") == 2
            captured = capsys.readouterr()
            assert captured.out == '{"outcome":"refused_or_uncertain"}\n' and captured.err == ""
            assert emissions == ([line] if mode in {"fresh_secret", "stderr_io"} else [])
            assert (reservation.read_bytes() if reservation.exists() else None) == reserved_bytes
            assert (receipt_path.read_bytes() if receipt_path.exists() else None) == expected_receipt
        assert writes == ([] if mode in {"pre_reservation", "old_state"} else [reservation.name]
                          if mode == "reservation_io" else [reservation.name, receipt_path.name])
        assert read_failures == ([] if mode in {"pre_reservation", "old_state", "reservation_io"}
                                 else ["direction_open_after_reservation"])
        assert formatted == admissions == offline.auth_calls == []
        assert case.api.calls == calls and case.downloads == downloads and case.api.commits == ["claim"]
        assert case.api.trees[case.api.head] == private_tree
        assert case.api.trees[case.api.head][case.prior] == case.prior_bytes
        assert {path: path.read_bytes() for path in protected} == protected
        assert not (case.root / "result").exists() and list((case.root / "observation").iterdir()) == []
        assert not (case.root / ("preparation" + ci.registration.HANDOFF_CONSUMED_SUFFIX)).exists()
        for data in [b"".join(text.encode() for text in emissions), expected_receipt or b""]:
            assert all(part.encode() not in data for part in (
                "synthetic-token", "Authorization", "/private/input.json", "provider-body", "SecretReadError", "SecretIOError"))
    finally:
        os.umask(previous_mask)
        ci.logging.disable(previous_logging)
