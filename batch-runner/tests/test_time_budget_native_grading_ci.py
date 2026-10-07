"""One fixed hosted route; synthetic HTTP/RPC/child/kernel facts, real validators.

The three full grading paths use the accepted native context and real F grade
serialization/checks. No private data, remote claim, judge or host proof occurs.
"""

from contextlib import contextmanager
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit

import httpx
import pytest
import yaml

import gpt54_time_budget_native_grading_ci as subject
from gpt54_prepared_input_attestation import _identity
from .test_gpt54_disposable_checkout import _FIXTURE_ENV
from .test_time_budget_native_grading_execution import (
    case, dual_roots, handoff_source_seed, handoff_sources, offline, _child,
)
from .test_time_budget_native_grading_intake import TOKEN, PRIVATE, NAMES
from .test_time_budget_first_v2_ci import PrivateStore, TOKEN as RPC_TOKEN

ROOT = Path(__file__).resolve().parents[2]
_REAL_RUN, _REAL_POPEN = subprocess.run, subprocess.Popen


@pytest.fixture
def hosted(case, offline, dual_roots, tmp_path, monkeypatch, record_property):
    """Execute the actual bootstrap Bash with explicitly synthetic R/F objects."""
    bootstrap, temporary = tmp_path / "ordinary-bootstrap", tmp_path / "runner-temp"
    temporary.mkdir(mode=0o700)
    environment = {**_FIXTURE_ENV, "GIT_ALLOW_PROTOCOL": "file", "GITHUB_WORKSPACE": str(bootstrap),
        "RUNNER_TEMP": str(temporary), "CONTROLLER_SHA": dual_roots["runtime_sha"],
        "CONTROLLER_TREE": case.request["controller"]["tree"], "GITHUB_ENV": str(tmp_path / "github-env")}
    Path(environment["GITHUB_ENV"]).touch(mode=0o600)

    def local(command, *, cwd=None, env=environment, check=True):
        with monkeypatch.context() as process:
            process.setattr(subprocess, "Popen", _REAL_POPEN)
            return _REAL_RUN(command, cwd=cwd, env=env, check=check, capture_output=True, timeout=30)

    local(["/usr/bin/git", "clone", "--shared", "--", str(dual_roots["runtime"]), str(bootstrap)])
    for root, sha in ((case.seed.runtime, case.seed.runtime_sha), (case.seed.frozen, case.seed.frozen_sha)):
        local(["/usr/bin/git", "-C", str(bootstrap), "fetch", "--no-tags", "--", str(root), sha])
    workflow = yaml.safe_load((ROOT / subject.WORKFLOW).read_text())
    block = next(step["run"] for step in workflow["jobs"][subject.JOB]["steps"]
                 if "git worktree add --detach" in step.get("run", ""))
    block = block.replace(subject.RETAINED["source"]["sha"], case.seed.runtime_sha)
    block = block.replace(subject.RETAINED["source"]["tree"], case.seed.runtime_tree)
    block = block.replace("882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2", case.seed.frozen_sha)
    block = block.replace("45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca", case.seed.frozen_tree)
    assert "AZURE_CONFIG_DIR" not in environment
    created = local(["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", block], cwd=bootstrap)
    assert created.returncode == 0
    roots = {key: temporary / basename for key, basename in subject.ROOT_NAMES.items()}
    propagated = dict(line.split("=", 1) for line in Path(environment["GITHUB_ENV"]).read_text().splitlines())
    assert propagated == {"AZURE_CONFIG_DIR": str(roots["login_root"])}
    assert roots["login_root"].stat().st_mode & 0o777 == 0o700 and list(roots["login_root"].iterdir()) == []
    previous_run = subprocess.run

    def named_local_git(command, **kwargs):
        if command[:2] == ["/usr/bin/git", "--no-replace-objects"]:
            position = command.index("-C")
            if Path(command[position + 1]) in {bootstrap, roots["controller_root"], roots["runtime_root"], roots["frozen_root"]}:
                assert command[position + 2] in {"rev-parse", "config", "ls-tree", "cat-file"}
                assert kwargs["timeout"] == 60 and kwargs["env"]["GIT_ALLOW_PROTOCOL"] == ""
                assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1" and "HF_TOKEN" not in kwargs["env"]
                kwargs["timeout"] = 30
                with monkeypatch.context() as process:
                    process.setattr(subprocess, "Popen", _REAL_POPEN)
                    return _REAL_RUN(command, **kwargs)
        return previous_run(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", named_local_git)
    for key, value in {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": subject.shared.REPOSITORY, "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": subject.shared.OWNER, "GITHUB_TRIGGERING_ACTOR": subject.shared.OWNER,
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_NUMBER": "4", "GITHUB_JOB": subject.JOB,
        "GITHUB_SHA": dual_roots["runtime_sha"], "TIME_BUDGET_GRADE_WORKFLOW_SHA": dual_roots["runtime_sha"],
        "GITHUB_WORKFLOW_REF": subject.shared.REPOSITORY + "/" + subject.WORKFLOW + "@refs/heads/main",
        "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "RUNNER_ENVIRONMENT": "github-hosted",
        "GITHUB_RUN_ID": "2001", "RUNNER_NAME": "synthetic-hosted-grade", "GITHUB_WORKSPACE": str(bootstrap),
        "RUNNER_TEMP": str(temporary), "AZURE_CONFIG_DIR": str(roots["login_root"]),
        "JE_ARROW_MALLOC_CONF": "background_thread:false", "AZURE_AI_ROUTE_PROFILE": "direct-v1",
        "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES": "1", "AZURE_AI_EXPECTED_DIRECT_ACCOUNT": case.seed.plan["shared"]["model"]["account"],
        "FOUNDRY_PROJECT_ENDPOINT": "https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/api/projects/gdpval-realworks",
        "CONTROLLER_SHA": dual_roots["runtime_sha"], "CONTROLLER_TREE": case.request["controller"]["tree"],
    }.items():
        monkeypatch.setenv(key, value)

    data = subject.bridge.reader._bytes(case.payload)
    completion = deepcopy(case.request["completion"])
    completion["result_identity"] = _identity(data)
    # Only explicit synthetic independent anchors replace historical values.
    monkeypatch.setattr(subject, "RETAINED", {key: completion[key] for key in subject.RETAINED})
    paths = subject._paths()
    request = {"format": subject.REQUEST_FORMAT, "purpose": subject.PURPOSE, "controller": case.request["controller"],
        "completion": completion, "cell": dict(subject.CELL), "frozen_source": case.request["frozen_source"],
        "input_registration": {**case.request["input_registration"], "sha256": case.seed.profile_sha},
        "registration_sha256": case.request["registration_sha256"], "dataset_sha256": case.request["dataset_sha256"],
        "step0": case.request["step0"], "deliverables": dict(subject.bridge.DELIVERABLES),
        "paths": {key: str(value) for key, value in paths.items()}, "policy": dict(subject.POLICY),
        "ci": {"repository": subject.shared.REPOSITORY, "workflow": subject.WORKFLOW, "ref": "refs/heads/main",
            "actor": subject.shared.OWNER, "job": subject.JOB, "attempt": 1, "run_number": 4,
            "runner": "ubuntu-24.04", "runner_os": "Linux", "runner_arch": "X64", "image": subject.GRADING_IMAGE},
        "storage": {"repository_name_sha256": subject.shared.TARGET_SHA256, "branch": subject.shared.BRANCH,
            "prefix": subject._namespace()[0], "expected_parent": "1" * 40},
        "not_before_unix": int(time.time()) - 5, "expires_unix": int(time.time()) + 1800}
    request_data = subject.bridge.reader._bytes(request)
    monkeypatch.setenv("TIME_BUDGET_GRADE_REQUEST_JSON", request_data.decode())
    monkeypatch.setenv("REQUEST_SHA256", _identity(request_data)["sha256"])
    arguments = {"request_json": request_data.decode(), "expected_request_sha256": _identity(request_data)["sha256"],
                 "controller_sha": request["controller"]["sha"], "controller_tree": request["controller"]["tree"]}
    cli = ["--controller-sha", arguments["controller_sha"], "--controller-tree", arguments["controller_tree"],
           "--expected-request-sha256", arguments["expected_request_sha256"]]
    store = PrivateStore(prefix=subject._namespace()[0])
    prior = subject.shared._namespace(subject.CELL)[0] + "/admission.json"
    store.trees[store.head][prior] = b"synthetic generation claim must remain immutable"
    store.writers[store.head][prior] = store.head
    state = SimpleNamespace(store=store, stages=[], original_gets=[], retained_gets=[], failures=[], fault=None,
        binding=None, handle=None, executor_arguments=None, children=[], closed=False, claim_guards=[], formatted=[])

    def observe(name, real):
        def call(*args, **kwargs):
            state.stages.append(name)
            record_property("first_operation", name)
            try:
                return real(*args, **kwargs)
            except BaseException as error:
                state.failures.append((name, error.args))
                record_property("refused_operation", name)
                raise
        return call

    for name in ("_originals", "_direction", "_claim", "_retain"):
        monkeypatch.setattr(subject, name, observe(name, getattr(subject, name)))
    real_preparation = subject.preparation.prepare_observation_grading

    def prepare(*args, **kwargs):
        assert "HF_TOKEN" not in os.environ and not any(os.environ.get(key) for key in subject.bridge.OTHER_CREDENTIALS)
        state.stages.append("real_F_preparer")
        if state.fault == "preparation":
            # Fail the actual original-result byte check, not a substituted verdict.
            result = kwargs["result_path"]
            result.write_bytes(result.read_bytes() + b" ")
        return real_preparation(*args, **kwargs)

    monkeypatch.setattr(subject.preparation, "prepare_observation_grading", observe("real_F_preparer", prepare))
    original_bytes = {"data/train-00000-of-00001.parquet": case.seed.parquet.read_bytes(),
        **{name: (case.seed.references / name).read_bytes() for name in case.seed.records},
        request["step0"]["member"]: case.seed.step0.read_bytes()}
    step0_repo = subject.registration.load_plan(case.seed.frozen / subject.registration.CODEX_TEMPLATE)["data"]["source"]

    @contextmanager
    def originals_http(method, url, **options):
        assert method == "GET" and options["max_retries"] == 0 and options["follow_redirects"] is False
        assert options["retry_on_exceptions"] == options["retry_on_status_codes"] == ()
        assert options["headers"]["authorization"] == "Bearer " + TOKEN and options["headers"]["Accept-Encoding"] == "identity"
        assert "HF_TOKEN" not in os.environ and urlsplit(url).netloc == "huggingface.co"
        prefixes = ["/datasets/openai/gdpval/resolve/" + case.seed.plan["shared"]["dataset"]["revision"] + "/",
                    "/datasets/" + step0_repo + "/resolve/" + request["step0"]["revision"] + "/"]
        path = unquote(urlsplit(url).path)
        matches = [prefix for prefix in prefixes if path.startswith(prefix)]
        assert len(matches) == 1
        member = path[len(matches[0]):]
        state.original_gets.append(member)
        body = original_bytes[member]
        if state.fault == "original" and member == request["step0"]["member"]:
            body = body[:-1] + b"x"
        yield SimpleNamespace(status_code=200, headers={"content-length": str(len(body))}, iter_raw=lambda **kw: iter((body,)))

    monkeypatch.setattr("huggingface_hub.utils.http_stream_backoff", originals_http)
    revision, target = completion["output_commit"], subject.shared.TARGET
    native_prefix, _, _ = subject.shared._namespace(subject.CELL)
    bodies = {f"/datasets/{target}/raw/{revision}/{native_prefix}/result/{subject.native.observation.RESULT}": data,
              **{f"/datasets/{target}/raw/{revision}/{native_prefix}/result/upload/{name}": value for name, value in case.files.items()}}

    class Transport(httpx.BaseTransport):
        def __init__(self, **kwargs):
            assert kwargs == {"retries": 0, "trust_env": False}

        def handle_request(self, outgoing):
            state.retained_gets.append(outgoing)
            assert len(state.retained_gets) <= 4 and outgoing.method == "GET"
            assert outgoing.headers["accept-encoding"] == "identity" and outgoing.headers["authorization"] == "Bearer " + TOKEN
            assert "HF_TOKEN" not in os.environ and all(0 < value <= 60 for value in outgoing.extensions["timeout"].values())
            if len(state.retained_gets) == 1:
                assert outgoing.url.path == f"/api/datasets/{target}/revision/{revision}"
                body = subject.bridge.reader._bytes({"id": target, "sha": revision, "private": True})
            else:
                body = bodies[outgoing.url.path]
            if state.fault == "file" and len(state.retained_gets) == 3:
                body = b"x" + body[1:]
            return httpx.Response(200, stream=httpx.ByteStream(body), request=outgoing)

    monkeypatch.setattr(httpx, "HTTPTransport", Transport)
    real_session = subject._session

    @contextmanager
    def storage_rpc(api):
        # Existing stateful HF RPC seam; object/blob/size/history/control and
        # permanent CAS validators are real, with no accepted-verdict stub.
        assert api is None and os.environ["HF_TOKEN"] == TOKEN
        assert subject.execution._NATIVE_INTAKES or state.fault == "guard_only"
        assert not any(os.environ.get(key) for key in subject.bridge.OTHER_CREDENTIALS)
        os.environ["HF_TOKEN"] = RPC_TOKEN
        try:
            with real_session(state.store) as values:
                yield values
        finally:
            os.environ["HF_TOKEN"] = TOKEN

    monkeypatch.setattr(subject, "_session", storage_rpc)
    return SimpleNamespace(case=case, workflow=workflow, paths=paths, request=request, arguments=arguments, cli=cli,
        state=state, offline=offline, local=local, data=data, prior=prior, bootstrap=bootstrap, block=block,
        environment=environment, original_step0=original_bytes[request["step0"]["member"]])


def _workflow(hosted, monkeypatch, capsys):
    workflow = hosted.workflow
    job = workflow["jobs"][subject.JOB]
    assert set(workflow.get("on", workflow.get(True))) == {"workflow_dispatch"}
    assert len(workflow["jobs"]) == 1 and job["runs-on"] == "ubuntu-24.04" and job["timeout-minutes"] == 270
    assert job["container"]["image"] == subject.GRADING_IMAGE
    assert workflow["permissions"] == {"contents": "read", "id-token": "write"}
    assert workflow["concurrency"] == {"group": "gpt54-time-budget-native-task3-frozen-grade", "cancel-in-progress": False}
    assert "HF_TOKEN" not in job["env"] and not any("runner." in str(value) for value in job["env"].values())
    steps = job["steps"]
    credentialed = [step for step in steps if "HF_TOKEN" in step.get("env", {})]
    assert len(credentialed) == 1 and credentialed[0]["id"] == "grade" and credentialed[0]["timeout-minutes"] == 252
    assert credentialed[0]["env"]["HF_TOKEN"] == "${{ secrets.HF_TOKEN }}"
    assert sum(step["timeout-minutes"] for step in steps) < 270
    source = next(step for step in steps if " validate-request " in step.get("run", ""))
    login = next(step for step in steps if step.get("uses", "").startswith("azure/login@"))
    assert steps.index(source) < steps.index(login) < steps.index(credentialed[0])
    assert steps[-1]["with"]["path"] == "${{ runner.temp }}/time-budget-task3-grade/completion.json"
    assert steps[-1]["if"] == "always() && steps.completion.outputs.validated == 'true'"
    for step, operation in ((source, "validate-request"), (credentialed[0], "run")):
        command = step["run"][step["run"].index("python3 "):]
        argv = [os.path.expandvars(part) for part in shlex.split(command.replace("\\\n", ""))]
        assert argv == ["python3", str(hosted.paths["controller_root"] / subject.HELPER), operation, *hosted.cli]
    assert subject.main(["validate-request", *hosted.cli]) == 0
    assert json.loads(capsys.readouterr().out) == {"outcome": "validated_not_execution_authority"}
    environment = {**hosted.environment, **{key: value for key, value in os.environ.items()
                   if key.startswith(("GITHUB_", "TIME_BUDGET_", "CONTROLLER_", "REQUEST_"))}}
    command = ["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", steps[0]["run"]]
    assert "HF_TOKEN" not in environment
    assert hosted.local(command, env=environment).returncode == 0
    assert hosted.local(command, env={**environment, "GITHUB_RUN_ATTEMPT": "2"}, check=False).returncode != 0
    assert hosted.local(["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", hosted.block],
                        cwd=hosted.bootstrap, check=False).returncode != 0


def _child_and_claim_observers(hosted, monkeypatch, record_property, scenario, tmp_path):
    state, paths = hosted.state, hosted.paths
    real_claim, real_execute = subject._claim, subject.execution.execute_native_task3_grading

    def claim(context, binding, routes, token):
        assert len(state.original_gets) == len(state.retained_gets) == 4 and len(hosted.offline.prepared) == 1
        assert "HF_TOKEN" not in os.environ and len(subject.execution._NATIVE_INTAKES) == 1
        assert list(paths["attempt_store"].iterdir()) == [] and state.children == []
        assert (paths["step0_manifest"]).read_bytes() == hosted.original_step0 and len(hosted.original_step0) == 218405
        state.binding = binding
        original = subject.execution._NATIVE_INTAKES.copy()
        state.handle = next(iter(original))
        origin = binding.as_dict()["grading_input_origin"]
        assert origin["original_result_identity"] == _identity(hosted.data)
        assert origin["derived_result_identity"] == _identity((paths["execution_input_directory"] / subject.preparation.RESULT).read_bytes())
        assert (paths["hydration_root"] / subject.native.observation.RESULT).read_bytes() == hosted.data
        assert (paths["preparation_root"] / subject.preparation.RESULT).read_bytes() == hosted.data
        if scenario == "success":
            good_store = state.store
            for mode in ("occupied", "parent", "lost"):
                guard_root = tmp_path / ("independent-synthetic-" + mode)
                guard_root.mkdir(mode=0o700)
                isolated = {**context, "paths": {**paths, "state_root": guard_root}}
                state.store = PrivateStore(prefix=subject._namespace()[0])
                if mode == "occupied":
                    state.store.trees[state.store.head][state.store.claim] = b"old consumed grade claim"
                elif mode == "parent":
                    isolated = {**isolated, "request": {**context["request"],
                        "storage": {**context["request"]["storage"], "expected_parent": "f" * 40}}}
                else:
                    commit = state.store.create_commit

                    class LostResponse(OSError):
                        def __str__(self):
                            state.formatted.append(True)
                            raise AssertionError("secret-bearing RPC exception formatted")

                    def lost_response(**kwargs):
                        commit(**kwargs)
                        raise LostResponse(PRIVATE + TOKEN)

                    state.store.create_commit = lost_response
                with pytest.raises(subject.NativeGradingCIRefused, match="^claim_unconfirmed_never_adopt_or_retry$"):
                    real_claim(isolated, binding, routes, token)
                assert state.store.commits == (["claim"] if mode == "lost" else [])
                assert "immutable_control_readback" not in state.store.calls and state.children == []
                assert list(paths["attempt_store"].iterdir()) == [] and not paths["destination"].exists()
                assert json.loads((guard_root / "claim-receipt.json").read_bytes())["outcome"] == "uncertain"
                state.claim_guards.append(mode)
            state.store = good_store
            assert subject.execution._NATIVE_INTAKES == original
        return real_claim(context, binding, routes, token)

    def execute(plan, **arguments):
        state.executor_arguments = arguments
        state.stages.append("real_native_executor")
        assert state.store.commits == ["claim"] and "immutable_control_readback" in state.store.calls
        assert "HF_TOKEN" not in os.environ and subject.execution._native_intake(arguments["native_preparation"])
        assert arguments["native_preparation"] is state.handle and len(subject.execution._NATIVE_INTAKES) == 1
        calls = _child(arguments, monkeypatch, mode="native" if scenario == "success" else scenario, record_property=record_property)
        state.children = calls
        result = real_execute(plan, **arguments)
        before = (paths["attempt_store"] / (subject.execution._observation_key(arguments["observation"]) + ".json")).read_bytes()
        # Only a refused local duplicate: the child and successful path are not repeated.
        with pytest.raises(subject.execution.GradingExecutionRefused, match="^grading_attempt_already_claimed$"):
            real_execute(plan, **{**arguments, "destination": paths["destination"].with_name("unused-alternate")})
        assert len(calls) == 1 and not paths["destination"].with_name("unused-alternate").exists()
        assert (paths["attempt_store"] / (subject.execution._observation_key(arguments["observation"]) + ".json")).read_bytes() == before
        return result

    monkeypatch.setattr(subject, "_claim", claim)
    monkeypatch.setattr(subject.execution, "execute_native_task3_grading", execute)


@pytest.mark.parametrize("scenario", ["guards", "original", "file", "preparation", "success", "partial", "timeout"])
def test_native_task3_hosted_grading_route(hosted, monkeypatch, capsys, record_property, tmp_path, scenario):
    state, paths = hosted.state, hosted.paths
    if scenario == "guards":
        _workflow(hosted, monkeypatch, capsys)
        for key, value in (("GITHUB_ACTOR", "wrong-owner"), ("GITHUB_TRIGGERING_ACTOR", "wrong-owner"),
                           ("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_RUN_NUMBER", "3"), ("GITHUB_SHA", "0" * 40),
                           ("TIME_BUDGET_GRADE_WORKFLOW_SHA", "0" * 40)):
            with monkeypatch.context() as drift:
                drift.setenv(key, value)
                assert subject.main(["run", *hosted.cli]) == 2
                assert json.loads(capsys.readouterr().out) == {"outcome": "refused_or_uncertain"}
        for mutation in ("digest", "cell", "source", "permission"):
            request = deepcopy(hosted.request)
            if mutation == "cell":
                request["cell"]["task_id"] = subject.native.CELL["task_id"]
            elif mutation == "source":
                request["completion"]["source"]["sha"] = "0" * 40
            elif mutation == "permission":
                request["policy"]["external_attempts"] = 2
            data = subject.bridge.reader._bytes(request)
            with monkeypatch.context() as drift:
                drift.setenv("TIME_BUDGET_GRADE_REQUEST_JSON", data.decode())
                cli = hosted.cli[:-1] + (["0" * 64] if mutation == "digest" else [_identity(data)["sha256"]])
                assert subject.main(["run", *cli]) == 2
                assert json.loads(capsys.readouterr().out) == {"outcome": "refused_or_uncertain"}
        assert state.original_gets == state.retained_gets == state.store.calls == []
        with monkeypatch.context() as drift:
            drift.setenv("HF_TOKEN", TOKEN)
            drift.setenv("OPENAI_API_KEY", PRIVATE)
            assert subject.main(["run", *hosted.cli]) == 2
            assert json.loads(capsys.readouterr().out) == {"outcome": "refused_or_uncertain"}
        assert state.original_gets == state.retained_gets == state.store.calls == []
        assert not paths["state_root"].exists() and subject.execution._NATIVE_INTAKES == {}
        record_property("bounded_outcome", "actual workflow bootstrap/source CLI; cheap source/caller/attempt/digest/cell/permission refusals before credentials or state")
        return

    if scenario in {"original", "file", "preparation"}:
        state.fault = scenario
    else:
        _child_and_claim_observers(hosted, monkeypatch, record_property, scenario, tmp_path)
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    record_property("operation", "actual_controller_CLI_run")
    status = subject.main(["run", *hosted.cli])
    captured = capsys.readouterr()
    assert status == (0 if scenario == "success" else 2), (state.stages, state.failures, captured)
    assert captured == ("", ""), (state.stages, state.failures, captured)
    result = json.loads((paths["state_root"] / "completion.json").read_bytes())
    assert "HF_TOKEN" not in os.environ and subject.execution._NATIVE_INTAKES == {}
    assert TOKEN not in json.dumps(result) and PRIVATE not in json.dumps(result)
    assert all(name not in json.dumps(result) for name in NAMES)
    assert result["usage"] is result["cost"] is result["quality_score"] is None
    assert result["retry_allowed"] is False and result["other_cells_graded"] == 0
    assert result["stdout_stderr"] == "discarded_by_accepted_executor_not_available"
    with subject.checked_request(**hosted.arguments, completion_only=True) as context:
        subject.validate_completion(result, context)
        for field in ("raw_error", "filename", "token", "grade_prose"):
            with pytest.raises(subject.NativeGradingCIRefused, match="^public_completion_schema_refused$"):
                subject.validate_completion({**result, field: PRIVATE + TOKEN}, context)
        with pytest.raises(subject.NativeGradingCIRefused, match="^public_terminal_refused$"):
            subject.validate_completion({**result, "terminal_reason": PRIVATE + TOKEN}, context)
        with pytest.raises(subject.NativeGradingCIRefused, match="^completion_is_not_execution_authority$"):
            subject.run(context)

    if scenario in {"original", "file", "preparation"}:
        assert result["status"] == "uncertain" and result["claim_commit"] is None and result["entry_invoked"] is None
        assert state.store.calls == state.store.commits == state.children == []
        assert list(paths["attempt_store"].iterdir()) == [] and not paths["destination"].exists()
        assert not (paths["state_root"] / "claim-reserved.json").exists()
        assert len(state.original_gets) == 4
        assert len(state.retained_gets) == {"original": 0, "file": 3, "preparation": 4}[scenario]
        assert len(hosted.offline.prepared) == (1 if scenario == "preparation" else 0)
        record_property("bounded_outcome", "real " + scenario + " byte validation refused before remote/local grade claim and child; partial state retained")
        return

    assert state.failures == ([("_claim", ("claim_unconfirmed_never_adopt_or_retry",))] * 3 if scenario == "success" else [])
    assert state.formatted == [] and len(state.children) == 1 and state.store.commits == ["claim", "output"]
    assert len(state.original_gets) == len(state.retained_gets) == 4 and len(hosted.offline.prepared) == 1
    assert state.stages.index("real_F_preparer") < state.stages.index("_claim") < state.stages.index("real_native_executor") < state.stages.index("_retain")
    assert result["status"] == {"success": "success", "partial": "partial", "timeout": "timeout"}[scenario]
    assert result["terminal_reason"] == {"success": "completed", "partial": "failed", "timeout": "timeout"}[scenario]
    assert result["retention"] == "acknowledged" and result["cleanup_confirmed"] is True
    assert result["grade_identity"] == _identity((paths["destination"] / "grade.json").read_bytes())
    assert state.store.trees[state.store.head][hosted.prior] == b"synthetic generation claim must remain immutable"
    assert state.store.writers[state.store.head][hosted.prior] == "1" * 40
    manifest = json.loads(state.store.trees[state.store.head][state.store.manifest])
    assert manifest["stdout_stderr"] == "discarded_by_accepted_executor_not_available"
    assert any("/_progress/" in role for role in manifest["files"]) is (scenario != "success")
    assert any(role.endswith(".cost_ledger.jsonl") for role in manifest["files"])
    assert all(TOKEN.encode() not in data and RPC_TOKEN.encode() not in data for data in state.store.trees[state.store.head].values())
    with pytest.raises(subject.execution.GradingExecutionRefused, match="^current_authenticated_native_intake_required$"):
        subject.execution._native_intake(state.handle)
    assert subject.main(["verify-completion", *hosted.cli]) == 0
    assert json.loads(capsys.readouterr().out) == {"outcome": "validated_not_execution_authority"}
    assert state.store.commits == ["claim", "output"] and len(state.children) == 1
    if scenario == "success":
        assert state.claim_guards == ["occupied", "parent", "lost"]
        outcome = json.loads((paths["destination"] / subject.execution.RESULT).read_bytes())
        with subject.checked_request(**hosted.arguments, completion_only=True) as context:
            uncertain = subject._completion(context, binding=state.binding,
                receipt={"returned_commit": result["claim_commit"]}, outcome=outcome,
                retained={"outcome": "uncertain", "returned_commit": None})
            subject.validate_completion(uncertain, context)
            assert uncertain["status"] == "uncertain" and uncertain["retention_commit"] is None
            assert uncertain["claim_commit"] == result["claim_commit"] and uncertain["retry_allowed"] is False
            with pytest.raises(subject.NativeGradingCIRefused, match="^unconfirmed_retention_is_uncertain$"):
                subject.validate_completion({**uncertain, "status": "success"}, context)
        # Actual retention byte scanner refuses a synthetic credential, without
        # retrying a grade, claim, HTTP hydration or successful retention.
        (paths["destination"] / "synthetic-leak").write_bytes(TOKEN.encode())
        with pytest.raises(subject.NativeGradingCIRefused, match="^credential_in_private_output$"):
            subject._snapshot({"paths": paths}, TOKEN)
    record_property("bounded_outcome", json.dumps({"scenario": scenario, "original_GETs": 4, "retained_GETs": 4,
        "child_calls": 1, "synthetic_step0_bytes": 218405, "kernel": "synthetic_not_host_support", "private_state": "synthetic_RPC",
        "remote_CAS_precedes_local_claim_and_child": True, "native_context_closed": True,
        "retention": result["retention"], "status": result["status"], "step8_seconds": 14400, "child_seconds": 14520}, sort_keys=True))
