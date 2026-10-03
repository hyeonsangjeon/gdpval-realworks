"""One opt-in offline integration: real originals, simulated provider records.

No verifier returns a canned verdict. Git, the historical compiler, serializers,
packet/stage/grader readers, approval predicates, CAS bytes/history, deadline and
owned-supervisor checks are real. GitHub/Azure/HF responses and the model process
are synthetic. The sole actual payload child is Python ``pass``.
"""

import base64
from copy import deepcopy
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import urllib.parse

import pytest
import yaml
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import codex_budget_pilot as owned
import codex_budget_pilot_ci as old_ci
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import codex_retention_ci as adapter
import codex_retention_diagnostic as registration
import codex_retention_first_cell as controller
import codex_retention_historical as historical
import codex_retention_prepare_packet as preparation
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from . import test_codex_budget_pilot as pilot_fixture
from .test_codex_budget_pilot import Clock
from .test_codex_budget_pilot_retention import MemoryHF, TOKEN
from .test_codex_ci_input_intake import GitHub, Response

REAL_POPEN = subprocess.Popen
REAL_RUN = subprocess.run
REAL_SLEEP = time.sleep
REAL_WAIT_CODES = tuple(method.__code__ for method in (
    REAL_POPEN._wait, REAL_POPEN.wait, REAL_POPEN._communicate, REAL_POPEN.communicate,
    REAL_POPEN.__exit__))


def positive(phase, call):
    try:
        return call()
    except Exception as error:
        frames = []
        frame = error.__traceback__
        while frame is not None:
            frames.append(Path(frame.tb_frame.f_code.co_filename).name + ":" + str(frame.tb_lineno)
                          + ":" + frame.tb_frame.f_code.co_name)
            frame = frame.tb_next
        safe = str(error) if isinstance(error, (adapter.RetentionCIRefused, controller.RetentionControllerRefused,
            historical.HistoricalSourceRefused, preparation.RetentionPreparationRefused,
            registration.RetentionRegistrationRefused)) else type(error).__name__
        pytest.fail(phase + ": " + safe + " at " + " -> ".join(frames), pytrace=False)


@pytest.fixture
def private_retention_opt_in():
    """Skip only absent opt-in, before any historical archive construction."""
    locator = os.environ.get("GDPVAL_RETENTION_PREPARED_HANDOFF")
    if locator is None:
        pytest.skip("explicit retained original-input handoff required; no fetch or synthetic pins")
    assert locator and Path(locator).is_file(), "required explicit private original-input handoff unavailable"


@pytest.fixture
def immutable_archives(private_retention_opt_in, tmp_path):
    """Only local immutable fixture construction precedes the shared guards."""
    archive, rematerialized = (tmp_path / name for name in (
        "immutable-input-observer", "independent-input-observer"))
    positive("immutable_historical_archive", lambda: historical.materialize_archive(archive))
    positive("independent_historical_archive", lambda: historical.materialize_archive(rematerialized))
    return archive, rematerialized


@pytest.fixture(autouse=True)
def offline(monkeypatch, immutable_archives):
    # Explicit dependency ordering, with the actual shared guard unchanged.
    # Production preparation/verifiers and the whole test still run guarded.
    pilot_fixture.offline.__wrapped__(monkeypatch)


class RetentionHF(MemoryHF):
    """The existing immutable CAS transport, seeded with synthetic old records."""

    def seed(self, revision, parent, files):
        self.trees[revision] = {**self.trees[parent], **files}
        self.writers[revision] = {**self.writers[parent], **{name: revision for name in files}}
        self.parents[revision] = parent
        self.head = revision


def _old_final(observation):
    api = RetentionHF()
    plan = observation["plan"]
    cell = plan["cells"][-1]
    inputs = observation["inputs"]
    host = {"policy": old_ci.HOST_POLICY, "instance_sha256": owned._digest("synthetic historical host"),
            "workflow": old_ci.WORKFLOW, "workflow_sha": historical.PRODUCER, "run_attempt": 1}
    binding = retained._binding(plan, cell, inputs, host=host,
        run={"id": historical.FINAL_RUN, "job": "cell", "attempt": 1})
    writer = {**plan, "ci": {**plan["ci"], "host": host}}
    state = owned._cell_state(writer, cell)
    state.update(status="failed", phase="finished", exit_code=0, child_invocations=1, reason="missing_result")
    completed = old_ci.completion(writer, cell, execute=True, state=state, inputs=inputs, cleanup=True)
    prior, claim_commit, output_commit, terminal_commit = (char * 40 for char in "abcd")
    api.seed(prior, api.head, {})
    claim = {"format": retained.CLAIM_FORMAT, "binding": binding, "expected_parent": prior,
        "predecessor": {"cell_id": plan["order"][-2], "terminal_commit": prior,
            "terminal_sha256": owned._digest("simulated previous terminal"), "output_commit": "e" * 40,
            "manifest_sha256": owned._digest("simulated previous manifest")}, "model_result": False, "grade": False}
    fields = ("campaign_id", "cell_id", "source_sha", "config_sha256", "plan_sha256", "order_sha256",
              "verified_inputs_sha256", "host_policy_sha256", "status", "exit_code", "reason", "timeout",
              "cleanup_confirmed", "receipt")
    manifest = {**{key: completed[key] for key in fields}, "format": output.FORMAT,
        "grade_ready": False, "grading_launched": False, "accounting": "missing", "files": [],
        "missing": ["bound_inference_result", "validated_deliverables", "bound_ledger_export", "usage"],
        "inference_branch": retained.BRANCH}
    cp, tp, prefix = retained._paths(cell)
    manifest_path = prefix + "/" + output.MANIFEST
    manifest_bytes = retained._encoded(manifest)
    terminal = {"format": retained.TERMINAL_FORMAT, "repository_name_sha256": retained.TARGET_SHA256,
        "inference_branch": retained.BRANCH, "claim_commit": claim_commit,
        "claim_identity": owned._identity(retained._encoded(claim)), "output_commit": output_commit,
        "manifest_identity": owned._identity(manifest_bytes), "publication_receipt_sha256": owned._digest("synthetic ack"),
        "publication_acknowledged": True, "output_objects": [retained._object(manifest_path, manifest_bytes)],
        "completion": completed}
    api.seed(claim_commit, prior, {cp: retained._encoded(claim)})
    api.seed(output_commit, claim_commit, {manifest_path: manifest_bytes})
    api.seed(terminal_commit, output_commit, {tp: retained._encoded(terminal)})
    return api


def _provider(document):
    run_id, source = document["provider"]["run_id"], document["source"]["head"]
    run = {"id": int(run_id), "url": adapter.API + run_id, "head_sha": source,
        "path": adapter.WORKFLOW, "event": "workflow_dispatch", "head_branch": "main", "run_attempt": 1,
        "status": "in_progress", "repository": {"full_name": adapter.REPOSITORY, "id": 4321,
            "owner": {"login": adapter.OWNER, "id": 1234}},
        "actor": {"login": adapter.OWNER, "id": 1234}, "triggering_actor": {"login": adapter.OWNER, "id": 1234}}
    jobs = {"total_count": 3, "jobs": [{"id": 700 + index, "name": name, "run_id": int(run_id),
        "head_sha": source, "run_attempt": 1, "status": "in_progress" if index == 2 else "completed",
        "conclusion": None if index == 2 else "success", "runner_id": 900 + index,
        "runner_name": "retention-synthetic-runner", "labels": ["ubuntu-22.04"]}
        for index, name in enumerate((adapter.PREPARE_JOB, adapter.APPROVE_JOB, adapter.EXECUTE_JOB))]}
    reviews = [{"state": "approved", "user": {"login": adapter.OWNER, "id": 1234},
        "comment": adapter.APPROVAL_PREFIX + owned._digest(document),
        "environments": [{"id": 35, "name": adapter.ENVIRONMENT}]}]
    return run, jobs, reviews


class Transport(adapter.LocalTransport):
    def __init__(self, document, api, signing_key, *, mode="ordinary"):
        self.document, self.api, self.mode = document, api, mode
        self.signing_key = signing_key
        self.provider = _provider(document)
        self.clock = Clock()
        self.github_calls, self.azure_calls, self.children = 0, 0, []
        self.harmless = False
        self.oidc_calls, self.oidc_fault = 0, None
        self.authority_responses = []

    def authority_opener(self):
        return self

    def open(self, request, *, timeout):
        """Raw HTTPS transport only; production parses and verifies everything."""
        assert 0 < timeout <= adapter.intake.REQUEST_TIMEOUT_SECONDS
        assert request.get_method() == "GET"
        url = request.full_url
        if url.startswith(adapter.API):
            self.github_calls += 1
            assert request.get_header("Authorization") == "Bearer synthetic-not-a-credential"
            urls = [adapter.API + self.document["provider"]["run_id"] + suffix
                    for suffix in ("", "/attempts/1/jobs?per_page=100", "/approvals")]
            data = json.dumps(self.provider[urls.index(url)]).encode()
        elif url == adapter.OIDC_JWKS:
            assert request.get_header("Authorization") is None
            numbers = self.signing_key.public_key().public_numbers()
            key = {"kid": "synthetic-key", "kty": "RSA", "alg": "RS256", "use": "sig",
                   "n": self.encoded(numbers.n.to_bytes(256, "big")), "e": "AQAB"}
            keys = [key, key] if self.oidc_fault == "duplicate_kid" else [key]
            data = json.dumps({"keys": keys}).encode()
        else:
            self.oidc_calls += 1
            assert request.get_header("Authorization") == "Bearer synthetic-never-passed-to-child"
            assert url.startswith(os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=")
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query, strict_parsing=True)
            assert set(query) == {"api-version", "audience"} and len(query["audience"]) == 1
            audience = query["audience"][0]
            now = int(time.time())
            claims = {"iss": adapter.OIDC_ISSUER, "aud": audience,
                "sub": "repo:" + adapter.REPOSITORY + ":ref:refs/heads/main",
                "repository": adapter.REPOSITORY, "repository_id": "4321", "repository_owner": adapter.OWNER,
                "repository_owner_id": "1234", "actor": adapter.OWNER, "actor_id": "1234",
                "ref": "refs/heads/main", "ref_type": "branch", "sha": self.document["source"]["head"],
                "workflow_ref": adapter.REPOSITORY + "/" + adapter.WORKFLOW + "@refs/heads/main",
                "workflow_sha": self.document["source"]["head"], "run_id": self.document["provider"]["run_id"],
                "run_attempt": "1", "event_name": "workflow_dispatch", "runner_environment": "github-hosted",
                "iat": now, "nbf": now - 60, "exp": now + 300, "jti": str(self.oidc_calls)}
            if self.oidc_fault == "other_boot":
                claims["aud"] = "urn:gdpval:retention-first-cell:" + owned._digest(self.document) + ":" + owned._digest(
                    {"job": 702, "runner": 902, "boot": "00000000-0000-4000-8000-000000000000"})
            elif self.oidc_fault == "wrong_source":
                claims["sha"] = "f" * 40
            elif self.oidc_fault == "wrong_repository":
                claims["repository_id"] = "9999"
            elif self.oidc_fault == "wrong_host":
                claims["runner_environment"] = "self-hosted"
            elif self.oidc_fault == "expired":
                claims["exp"] = now - 1
            elif self.oidc_fault == "future_nbf":
                claims["nbf"] = now + 300
            header = b'{"typ":"JWT","alg":"RS256","kid":"synthetic-key","x5t":"synthetic-thumbprint"}'
            if self.oidc_fault == "duplicate_json":
                header = b'{"typ":"JWT","alg":"RS256","alg":"RS256","kid":"synthetic-key"}'
            elif self.oidc_fault == "algorithm":
                header = b'{"typ":"JWT","alg":"HS256","kid":"synthetic-key"}'
            signed = self.encoded(header) + "." + self.encoded(json.dumps(claims).encode())
            signature = self.signing_key.sign(signed.encode(), padding.PKCS1v15(), hashes.SHA256())
            if self.oidc_fault == "signature":
                signature = bytes([signature[0] ^ 1]) + signature[1:]
            data = json.dumps({"value": signed + "." + self.encoded(signature)}).encode()
        response = Response(data, url=url, content_type="application/json",
                            status=302 if self.oidc_fault == "redirect" else 200)
        self.authority_responses.append(response)
        return response

    @staticmethod
    def encoded(data):
        return base64.urlsafe_b64encode(data).decode().rstrip("=")

    def azure(self, arguments):
        self.azure_calls += 1
        identity = adapter.azure_identity.expected_identity(os.environ)
        if arguments == ["account", "show", "--output", "json"]:
            return json.dumps({"tenantId": identity["tenant"], "id": identity["subscription"]})
        assert arguments == ["account", "get-access-token", "--scope", adapter.azure_identity.AI_SCOPE,
                             "--query", "accessToken", "--output", "tsv"]
        # Raw synthetic external response, not a patched identity verdict.
        value = {"aud": adapter.azure_identity.AI_AUDIENCE, "nbf": time.time() - 30,
                 "exp": time.time() + 300, "tid": identity["tenant"], "azp": identity["client"]}
        return "synthetic." + base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=") + ".synthetic"

    def owned_process(self, command, **options):
        assert self.api.commits == ["admission"]
        assert command == [sys.executable, "step2_run_inference.py", "--condition", "condition_a",
                           "--codex-deadline-state", str(options["ownership"][0].parent / "deadline")]
        assert options["cwd"] == controller.ROOT / "batch-runner"
        env = options["env"]
        assert not {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "PYTHONPATH", "PYTHONHOME",
                    "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL"} & env.keys()
        assert env["GDPVAL_RELAY_LINEAGE_ID"] == registration.compile_plan()["cells"][0]["config"]["experiment"]["id"]
        host = options["ownership"][0].parent
        assert env["GDPVAL_CODEX_RUN_ROOT"] == str(host / "native-workspaces")
        assert options["timeout"] == 10860
        self.children.append(tuple(command))
        path, binding = options["ownership"]
        if self.mode == "cleanup":
            owned._save(path, {**owned._owner_state(binding["plan_sha256"]), **binding,
                "phase": "running", "pid": 4242, "tree_reaped": False, "owner_reaped": False})
            raise owned.OwnedChildCleanupRefused("owned_child_cleanup_unconfirmed")
        if self.mode == "start_unknown":
            owned._save(path, {**owned._owner_state(binding["plan_sha256"]), **binding,
                "phase": "launching", "tree_reaped": False, "owner_reaped": False})
            raise OSError("synthetic_start_ack_unknown")
        if self.mode == "harmless":
            self.harmless = True
            try:
                return owned.LocalTransport.process(self, [sys.executable, "-c", "pass"], **options)
            finally:
                self.harmless = False
        owned._save(path, {**owned._owner_state(binding["plan_sha256"]), **binding,
            "phase": "reaped", "pid": 4242, "tree_reaped": True, "owner_reaped": True, "exit_code": 0})
        return subprocess.CompletedProcess(command, 0)


def _assert_retention_execution_workflow_contract():
    workflow = yaml.safe_load((controller.ROOT / adapter.WORKFLOW).read_text())
    jobs = workflow["jobs"]
    dispatch = workflow.get("on", workflow.get(True))["workflow_dispatch"]["inputs"]
    assert dispatch["prepare"]["default"] is False and dispatch["execute"]["default"] is False
    assert set(jobs) == {adapter.PREPARE_JOB, adapter.APPROVE_JOB, adapter.EXECUTE_JOB}
    assert jobs[adapter.APPROVE_JOB]["environment"] == {"name": "grading"}
    assert "environment" not in jobs[adapter.EXECUTE_JOB]
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in jobs[adapter.PREPARE_JOB] and jobs[adapter.APPROVE_JOB]["permissions"] == {}
    assert jobs[adapter.EXECUTE_JOB]["permissions"] == {"contents": "read", "actions": "read", "id-token": "write"}
    assert workflow["concurrency"] == {"group": "codex-budget-pilot-ci-20260923-01", "cancel-in-progress": False}
    executable = jobs[adapter.EXECUTE_JOB]["steps"][-1]
    assert "codex_retention_task5_fresh_r2.py --execute" in executable["run"]
    assert '--request-sha256 "$APPROVED_REQUEST_SHA256"' in executable["run"]
    assert set(executable["env"]) == {"GITHUB_TOKEN", "HF_TOKEN", "AZURE_AI_ROUTE_PROFILE",
                                     "FOUNDRY_PROJECT_ENDPOINT", "CODEX_FOUNDRY_CONNECTION_CONFIRMED"}


def test_retention_ci_grant_cas_and_owned_runtime_are_bound(tmp_path, monkeypatch, capsys, immutable_archives):
    locator = os.environ.get("GDPVAL_RETENTION_PREPARED_HANDOFF")
    assert locator and Path(locator).is_file(), "required explicit private original-input handoff unavailable"
    handoff = preparation._json_object(preparation._read(Path(locator), "private_fixture_handoff"))
    originals = preparation.PreparedInputs(Path(handoff["destination"]), Path(handoff["original_parquet"]),
                                           Path(handoff["reference_root"]), Path(handoff["step0_manifest"]))
    forbidden_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        raise AssertionError("retention integration crossed a live boundary")

    for name in ("core.codex_runner.CodexAgentRunner.__init__", "core.executor.TaskExecutor.__init__",
                 "prepare_dataset.snapshot_download", "prepare_dataset.load_dataset", "step8_grade.RubricLoader.__init__",
                 "huggingface_hub.HfApi.create_commit", "huggingface_hub.HfApi.repo_info"):
        monkeypatch.setattr(name, forbidden)
    monkeypatch.setattr(CodexTaskDeadline, "admit_attempt", forbidden)
    transports = []
    archive, rematerialized = immutable_archives
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    allowed_children, allowed_waits = {}, set()
    denied_sleep = time.sleep
    git_metadata = {
        ("rev-parse", "HEAD"), ("rev-parse", "HEAD^{tree}"),
        ("rev-parse", "--show-toplevel"),
        ("rev-parse", "--path-format=absolute", "--git-common-dir"),
        ("status", "--porcelain", "--untracked-files=normal"),
        ("config", "--name-only", "--get-regexp",
         r"^(filter\.|include\.|includeif\.|extensions\.partialclone$|remote\..*\.promisor$|core\.alternaterefscommand$)"),
        ("archive", "--format=tar", historical.SOURCE, "batch-runner", ".github/workflows"),
    }

    def allowlisted_wait_sleep(delay):
        frame = sys._getframe(1)
        if frame.f_code is not REAL_WAIT_CODES[0]:
            return denied_sleep(delay)
        process = frame.f_locals.get("self")
        if type(process) is not REAL_POPEN or process not in allowed_children:
            return denied_sleep(delay)
        bound, waiting, frames = allowed_children[process], frame.f_locals, {}
        # Both communicate wait sites and stdlib exception/context cleanup must
        # lead to this exact still-active owner frame, never an unrelated thread.
        while frame is not bound["owner"]:
            if (frame is None or not any(frame.f_code is code for code in REAL_WAIT_CODES)
                    or frame.f_locals.get("self") is not process):
                return denied_sleep(delay)
            frames[frame.f_code] = frame.f_locals
            frame = frame.f_back
        owner = frame.f_locals
        if not (owner.get("process") is process and tuple(process.args) == bound["command"]
                and 0 < waiting["timeout"] <= bound["timeout"]
                and delay == waiting["delay"] and 0 < delay <= 0.05
                and (bound["cwd"] is not None or Path.cwd() == bound["inherited_cwd"])):
            return denied_sleep(delay)
        if frame.f_code is REAL_RUN.__code__:
            if not (owner["timeout"] == bound["timeout"]
                    and tuple(owner["popenargs"][0]) == bound["command"]
                    and owner["kwargs"].get("cwd") == bound["cwd"]):
                return denied_sleep(delay)
            communication, exchange = (frames.get(code) for code in (REAL_WAIT_CODES[3], REAL_WAIT_CODES[2]))
            if communication is not None:
                if not (communication["timeout"] == bound["timeout"] and communication["endtime"] is not None
                        and bound["deadline"] in (None, communication["endtime"])
                        and (exchange is None or (exchange["orig_timeout"] == bound["timeout"]
                             and exchange["endtime"] == communication["endtime"]))):
                    return denied_sleep(delay)
                bound["deadline"] = communication["endtime"]
        elif not (frame.f_code is owned.LocalTransport.process.__code__
                  and owner["timeout"] == bound["timeout"] and owner["until"] == bound["deadline"]
                  and owner["options"].get("cwd") == bound["cwd"]):
            return denied_sleep(delay)
        if bound["deadline"] is None:
            return denied_sleep(delay)
        remaining = bound["deadline"] - time.monotonic()
        if remaining > 0:
            allowed_waits.add(bound["kind"])
            return REAL_SLEEP(min(delay, remaining))
        # Let the unchanged stdlib loop raise TimeoutExpired and run reap its own
        # child; no unbounded cleanup wait requires this sleep exception.

    def metadata_or_harmless_only(command, **options):
        # Narrow subprocess TRANSPORT allowlist. All source/identity validators
        # still run, including actual Git cleanliness and immutable archive data.
        runner = sys._getframe(1)
        deadline = None
        if command[0] == "/usr/bin/git":
            index = command.index("-C")
            assert Path(command[index + 1]) == controller.ROOT
            verb = command[index + 2]
            assert verb in {"rev-parse", "status", "config", "archive"}
            if verb == "archive":
                assert command[index + 2:] == ["archive", "--format=tar", historical.SOURCE, "batch-runner", ".github/workflows"]
            assert options["env"]["GIT_NO_LAZY_FETCH"] == "1" and options["env"]["GIT_ALLOW_PROTOCOL"] == ""
            assert tuple(command[index + 2:]) in git_metadata
            assert runner.f_code is REAL_RUN.__code__ and runner.f_back.f_code is owned._git.__code__
            assert runner.f_locals["timeout"] == 60
            assert options == {"stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE,
                               "stderr": subprocess.PIPE, "env": runner.f_back.f_locals["environment"]}
            cwd = Path.cwd()
            assert cwd == controller.ROOT / "batch-runner"
            kind, timeout = "git", 60
        elif command[:2] == [sys.executable, "-c"]:
            assert command[2] in {historical.SAFE_ERROR + historical.OBSERVE, historical.SAFE_ERROR + historical.MATERIALIZE}
            assert options["cwd"] in {root / "batch-runner" for root in (archive, rematerialized)}
            assert command[3:] == [str(originals.dataset_parquet), str(originals.reference_root), str(originals.step0_manifest)]
            assert set(options["env"]) == {"PATH", "LANG", "PYTHONDONTWRITEBYTECODE", "HF_HUB_OFFLINE",
                                            "HF_DATASETS_OFFLINE", "TRANSFORMERS_OFFLINE", "PYTHONNOUSERSITE",
                                            "GDPVAL_RELAY_LINEAGE_ID"}
            assert options["env"]["GDPVAL_RELAY_LINEAGE_ID"] == historical.INPUT_LINEAGE
            assert runner.f_code is REAL_RUN.__code__ and runner.f_back.f_code is historical._command.__code__
            assert runner.f_locals["timeout"] == 90
            assert options == {"cwd": runner.f_back.f_locals["root"] / "batch-runner",
                               "env": runner.f_back.f_locals["environment"],
                               "stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
            kind = "historical_observe" if command[2] == historical.SAFE_ERROR + historical.OBSERVE else "historical_materialize"
            timeout = 90
        else:
            assert any(transport.harmless for transport in transports)
            assert command[:3] == [sys.executable, str(Path(owned.__file__).absolute()), owned.OWNED_CHILD_ARG]
            assert command[5:] == [sys.executable, "-c", "pass"]
            assert options["start_new_session"] is True
            assert runner.f_code is owned.LocalTransport.process.__code__
            assert runner.f_back.f_code is Transport.owned_process.__code__
            lifecycle = runner.f_locals
            assert any(transport is lifecycle["self"] and transport.harmless for transport in transports)
            assert lifecycle["command"] == [sys.executable, "-c", "pass"]
            assert command[3:5] == [str(lifecycle["inherited"].fileno()), str(lifecycle["lock"])]
            assert options == {**lifecycle["options"], "start_new_session": True,
                               "pass_fds": (lifecycle["lock"], lifecycle["inherited"].fileno())}
            assert options["cwd"] == controller.ROOT / "batch-runner" and lifecycle["timeout"] == 10860
            kind, timeout, deadline = "owned_supervisor", lifecycle["timeout"], lifecycle["until"]
        # One registration path; no alternate wait/reaper or child implementation.
        # The supervisor's existing poll/wakeup reap and its exact pass payload
        # do not call timed stdlib wait, but retain their real lifecycle binding.
        binding = {"command": tuple(command), "cwd": options.get("cwd"),
            "inherited_cwd": Path.cwd(), "owner": runner, "timeout": timeout, "deadline": deadline, "kind": kind}
        process = REAL_POPEN(command, **options)
        allowed_children[process] = binding
        return process

    # subprocess.run itself is left real only for the Popen-allowlisted metadata
    # commands. A shell, model command, credential query or other PID is refused.
    monkeypatch.setattr(subprocess, "run", REAL_RUN)
    monkeypatch.setattr(subprocess, "Popen", metadata_or_harmless_only)
    monkeypatch.setattr(time, "sleep", allowlisted_wait_sleep)
    guarded_sleep = time.sleep
    with pytest.raises(AssertionError, match="^dispatcher regression crossed a live boundary$"):
        time.sleep(0)
    with pytest.raises(AssertionError):
        subprocess.run([sys.executable, "-c", "pass"], timeout=60)
    for lookalike in (
        [sys.executable, "-c", historical.SAFE_ERROR + historical.OBSERVE + "\n# unregistered"],
        [sys.executable, str(Path(owned.__file__).absolute()), owned.OWNED_CHILD_ARG,
         "0", "0", sys.executable, "-c", "pass"],
        [sys.executable, "step2_run_inference.py", "--condition", "condition_a"],
    ):
        with pytest.raises(AssertionError):
            subprocess.run(lookalike, timeout=60)
    assert not allowed_children
    host_parent = Path(tempfile.mkdtemp(prefix=".retention-ci-test-host-", dir=Path(__file__).resolve().parents[3]))
    monkeypatch.setenv("GDPVAL_CODEX_RUN_ROOT", str(host_parent / "agent-native"))
    monkeypatch.setenv("TMPDIR", str(host_parent / "agent-temp"))
    source = owned._git(controller.ROOT, "rev-parse", "HEAD").stdout.decode().strip()
    environment = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": adapter.REPOSITORY,
        "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": source, "RETENTION_WORKFLOW_SHA": source, "GITHUB_RUN_ID": "700000001",
        "GITHUB_JOB": adapter.EXECUTE_JOB, "RUNNER_OS": "Linux", "ImageOS": "ubuntu22",
        "RUNNER_NAME": "retention-synthetic-runner",
        "GITHUB_WORKFLOW_REF": adapter.REPOSITORY + "/" + adapter.WORKFLOW + "@refs/heads/main",
        "CODEX_FOUNDRY_CONNECTION_CONFIRMED": "1", "AZURE_AI_ROUTE_PROFILE": "direct-v1",
        "FOUNDRY_PROJECT_ENDPOINT": "https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/api/projects/synthetic",
        "HF_TOKEN": TOKEN, "GITHUB_TOKEN": "synthetic-not-a-credential",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "synthetic-never-passed-to-child",
        "ACTIONS_ID_TOKEN_REQUEST_URL": "https://pipelines.actions.githubusercontent.com/00000000-0000-4000-8000-000000000001"
            "/_apis/distributedtask/hubs/build/plans/00000000-0000-4000-8000-000000000002"
            "/jobs/00000000-0000-4000-8000-000000000003/idtoken?api-version=2.0"}
    for index, role in enumerate(("CLIENT", "TENANT", "SUBSCRIPTION"), 1):
        environment["AZURE_AI_EXPECTED_" + role + "_ID"] = f"0000000{index}-0000-4000-8000-00000000000{index}"
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    with monkeypatch.context() as no_admission:
        no_admission.setattr(CodexTaskDeadlineStore, "__init__", forbidden)
        no_admission.setattr(CodexTaskDeadline, "admit_attempt", forbidden)
        positive("guarded_immutable_historical_archive", lambda: historical.verify_archive(archive))
        unexpected = archive / "batch-runner/json.py"
        unexpected.write_bytes(b'raise AssertionError("unexpected code must never run")\n')
        try:
            with pytest.raises(historical.HistoricalSourceRefused, match="^historical_unexpected_member_refused$"):
                historical.observe(archive, originals)
        finally:
            unexpected.unlink()
        positive("genuine_offline_original_five_serializer", lambda: historical.materialize_originals(archive, originals))
        sources = replace(originals, prepared_root=archive)
        controller.WORKSPACE_DIR.mkdir(mode=0o700, exist_ok=True)
        request = controller.Request(controller.FIRST_CELL_ID, sources, controller.ROOT / adapter.PACKET_ROLE,
            controller.ROOT, preparation.source_identity()["sha256"], controller.source_identity()["sha256"])
        positive("real_current_packet", lambda: preparation.prepare_packet(cell_id=request.cell_id, sources=sources,
            output=request.packet, expected_preparer_sha256=request.expected_preparer_sha256))
        positive("real_current_step2_stage", lambda: controller.stage_runtime(request))
        document, observation = positive("real_request_and_old_compiler", lambda: adapter.canonical_request(
            request, reviewed_source_sha=source, run_id=environment["GITHUB_RUN_ID"], historical_root=archive))
        positive("guarded_independent_historical_archive", lambda: historical.verify_archive(rematerialized))
        positive("independent_original_five_serializer", lambda: historical.materialize_originals(rematerialized, originals))
        positive("independent_prepared_byte_equality", lambda: preparation._same(
            "independent_prepared_bytes_changed", (archive / preparation.PREPARED_PATH).read_bytes(),
            (rematerialized / preparation.PREPARED_PATH).read_bytes()))
        independent, independent_observation = positive("independent_request_identity", lambda: adapter.canonical_request(
            replace(request, sources=replace(originals, prepared_root=rematerialized)), reviewed_source_sha=source,
            run_id=environment["GITHUB_RUN_ID"], historical_root=rematerialized))
        assert independent == document and independent_observation == observation
        assert document["input_roles_sha256"] == preparation.ORIGINAL_INPUT_ROLES_SHA256
        assert document["scope"] == adapter.SCOPE and document["grading"]["materialized_grader_source_sha256"] != registration.BASE_GRADER_TEMPLATE_SOURCE_SHA256
        assert document["historical_observer_source"] == historical.SOURCE
        assert document["historical_producer_source"] == historical.PRODUCER
        assert document["source"]["head"] == source and document["source"]["adapter"]["reviewed"] is False
        grant = adapter.ExecutionGrantRequest(source, owned._digest(document), archive)
        base_api = _old_final(observation)
        old_trees = deepcopy(base_api.trees)
        api = deepcopy(base_api)
        transport = Transport(document, api, signing_key)
        transports.append(transport)
        refused_host = host_parent / "not-admitted"
        with pytest.raises(controller.RetentionControllerRefused, match="^retention_execution_grant_required$"):
            controller.execute_first_cell(request, host_state=refused_host)
        for wrong in (True, {"approved": True}, {"request_sha256": grant.request_sha256}):
            with pytest.raises(adapter.RetentionCIRefused, match="^retention_execution_grant_required$"):
                controller.execute_first_cell(request, host_state=refused_host, grant=wrong,
                                               _test_transport=transport, _test_api=api)
        with pytest.raises(adapter.RetentionCIRefused, match="^clean_exact_retention_source_required$"):
            controller.execute_first_cell(request, host_state=refused_host, grant=replace(grant, reviewed_source_sha="f" * 40),
                                           _test_transport=transport, _test_api=api)
        with pytest.raises(controller.RetentionControllerRefused, match="^only_first_or_task4_fresh_r1_supported$"):
            controller.execute_first_cell(replace(request, cell_id=registration.compile_plan()["order"][4]),
                host_state=refused_host, grant=grant, _test_transport=transport, _test_api=api)
        with pytest.raises(adapter.RetentionCIRefused, match="^approved_retention_request_changed$"):
            controller.execute_first_cell(request, host_state=refused_host, grant=replace(grant, request_sha256="0" * 64),
                                           _test_transport=transport, _test_api=api)
        wrong_parquet = tmp_path / "wrong-original.parquet"
        wrong_parquet.write_bytes(b"synthetic wrong input, never a private payload")
        with pytest.raises(preparation.RetentionPreparationRefused, match="^original_parquet_bytes_refused:ReferenceIntegrityError$"):
            controller.execute_first_cell(replace(request, sources=replace(sources, dataset_parquet=wrong_parquet)),
                host_state=refused_host, grant=grant, _test_transport=transport, _test_api=api)
        staged_bytes = controller.STAGED.read_bytes()
        try:
            controller.STAGED.write_bytes(staged_bytes + b"\n")
            with pytest.raises(controller.RetentionControllerRefused, match="^staging_readback_mismatch$"):
                controller.execute_first_cell(request, host_state=refused_host, grant=grant,
                                               _test_transport=transport, _test_api=api)
        finally:
            controller.STAGED.write_bytes(staged_bytes)
        assert not refused_host.exists() and api.commits == [] and transport.children == []
        # Every negative uses the real provider-data verifier, not a replacement
        # verdict or local approval string. No claim, clock or child may occur.
        for changed, reason in (
            (lambda run, jobs, reviews: run.update(head_sha="f" * 40), "authenticated_retention_run_mismatch"),
            (lambda run, jobs, reviews: jobs["jobs"][-1].update(runner_name="other"), "authenticated_execution_runner_mismatch"),
            (lambda run, jobs, reviews: reviews[0].update(comment=adapter.APPROVAL_PREFIX + "0" * 64), "owner_environment_request_approval_mismatch"),
            (lambda run, jobs, reviews: reviews[0].update(state="rejected"), "owner_environment_request_approval_mismatch"),
            (lambda run, jobs, reviews: reviews[0]["user"].update(login="other"), "owner_environment_request_approval_mismatch"),
            (lambda run, jobs, reviews: reviews.append(deepcopy(reviews[0])), "unambiguous_owner_environment_review_required"),
        ):
            transport.provider = _provider(document)
            changed(*transport.provider)
            with pytest.raises(adapter.RetentionCIRefused, match="^" + reason + "$"):
                controller.execute_first_cell(request, host_state=refused_host, grant=grant,
                                               _test_transport=transport, _test_api=api)
            assert not refused_host.exists() and api.commits == [] and transport.children == []
        transport.provider = _provider(document)
        with monkeypatch.context() as other_route:
            other_route.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://other.services.ai.azure.com/api/projects/synthetic")
            with pytest.raises(adapter.RetentionCIRefused, match="^retention_registered_route_required$"):
                controller.execute_first_cell(request, host_state=refused_host, grant=grant,
                                               _test_transport=transport, _test_api=api)
            assert not refused_host.exists() and api.commits == [] and transport.children == []
        for fault, reason in (
            ("signature", "github_oidc_signature_refused"),
            ("wrong_source", "github_oidc_scope_mismatch"),
            ("wrong_repository", "github_oidc_scope_mismatch"),
            ("wrong_host", "github_oidc_scope_mismatch"),
            ("other_boot", "github_oidc_scope_mismatch"),
            ("expired", "github_oidc_time_refused"),
            ("future_nbf", "github_oidc_time_refused"),
            ("algorithm", "github_oidc_header_refused"),
            ("duplicate_json", "github_job_token_json_refused"),
            ("duplicate_kid", "github_oidc_key_id_refused"),
            ("redirect", "github_authority_origin_or_status_refused"),
        ):
            transport.oidc_fault = fault
            response_start = len(transport.authority_responses)
            with pytest.raises(adapter.RetentionCIRefused, match="^" + reason + "$"):
                controller.execute_first_cell(request, host_state=refused_host, grant=grant,
                                               _test_transport=transport, _test_api=api)
            assert not refused_host.exists() and api.commits == [] and transport.children == []
            responses = transport.authority_responses[response_start:]
            assert responses and all(response.closed for response in responses)
            if fault == "redirect":
                assert len(responses) == 1 and responses[0].status == 302 and responses[0].reads == []
        transport.oidc_fault = None
        # Only raw external responses are substituted. The shared transport
        # guard and adapter's status/header/body/JSON predicates remain real.
        authority_url = adapter.API + environment["GITHUB_RUN_ID"]
        read_authority = lambda: transport._authority_json(authority_url, token=None,
            deadline=time.monotonic() + adapter.intake.TRANSFER_TIMEOUT_SECONDS)
        for response, reason, body_read in (
            (Response(b"{}", url=authority_url, content_type="application/json"), None, True),
            (Response(b"unread foreign body", url="https://example.invalid/authority"),
             "github_authority_origin_or_status_refused", False),
            (Response(b"unread paginated body", url=authority_url, headers=[("Link", "synthetic-next")]),
             "github_authority_pagination_refused", False),
            (Response(b"{", url=authority_url, content_type="application/json"),
             "github_authority_json_refused", True),
        ):
            opener = GitHub([response])
            with monkeypatch.context() as response_transport:
                response_transport.setattr(transport, "authority_opener", lambda: opener)
                if reason is None:
                    assert read_authority() == {}
                else:
                    with pytest.raises(adapter.RetentionCIRefused, match="^" + reason + "$"):
                        read_authority()
            assert response.closed and bool(response.reads) is body_read
            assert len(opener.calls) == 1
            assert not refused_host.exists() and api.commits == [] and transport.children == []
        for failure in ("open", "read", "close", "redirect_close"):
            response = None if failure == "open" else Response(b"{}", url=authority_url,
                content_type="application/json", status=302 if failure == "redirect_close" else 200)
            opener = GitHub([OSError("synthetic acquisition detail") if response is None else response])

            def failed_io(*args, **kwargs):
                raise OSError("synthetic response detail")

            def failed_close():
                Response.close(response)
                failed_io()

            with monkeypatch.context() as response_transport:
                response_transport.setattr(transport, "authority_opener", lambda: opener)
                if failure == "read":
                    response_transport.setattr(response, "read1", failed_io)
                elif failure in {"close", "redirect_close"}:
                    response_transport.setattr(response, "close", failed_close)
                with pytest.raises(adapter.intake.InputIntakeRefused,
                                   match="^private_input_verification_or_transport_failed$"):
                    read_authority()
            assert response is None or response.closed
            if failure == "redirect_close":
                assert response.reads == []
            assert len(opener.calls) == 1
            assert not refused_host.exists() and api.commits == [] and transport.children == []
        with monkeypatch.context() as missing_credential:
            missing_credential.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
            previous = transport.oidc_calls
            with pytest.raises(adapter.RetentionCIRefused, match="^github_job_issuance_credential_required$"):
                controller.execute_first_cell(request, host_state=refused_host, grant=grant,
                                               _test_transport=transport, _test_api=api)
            assert transport.oidc_calls == previous and not refused_host.exists() and api.commits == []
        for locator in ("https://example.invalid/idtoken", environment["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=other",
                        environment["ACTIONS_ID_TOKEN_REQUEST_URL"].replace(".actions.githubusercontent.com", ".actions.githubusercontent.com.example.invalid")):
            with monkeypatch.context() as wrong_origin:
                wrong_origin.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", locator)
                with pytest.raises(adapter.RetentionCIRefused, match="^github_job_issuance_locator_refused$"):
                    controller.execute_first_cell(request, host_state=refused_host, grant=grant,
                                                   _test_transport=transport, _test_api=api)
                assert not refused_host.exists() and api.commits == [] and transport.children == []
        for flag in ("conflict", "unknown"):
            candidate = deepcopy(base_api)
            candidate.move_before_commit = flag == "conflict"
            candidate.lost = "admission" if flag == "unknown" else None
            synthetic = Transport(document, candidate, signing_key)
            transports.append(synthetic)
            host = host_parent / ("claim-" + flag)
            with pytest.raises(adapter.RetentionCIRefused, match="^retention_claim_unresolved:"):
                controller.execute_first_cell(request, host_state=host, grant=grant,
                                               _test_transport=synthetic, _test_api=candidate)
            assert candidate.commits == ["admission"] and synthetic.children == [] and not (host / "deadline").exists()
            assert retained._read(host / "remote-admission-receipt.json")["outcome"] == "unresolved"

    observed = []
    for mode in ("harmless", "cleanup", "start_unknown", "output_unknown", "terminal_unknown"):
        api = deepcopy(base_api)
        if mode in {"output_unknown", "terminal_unknown"}:
            api.lost = mode.split("_")[0]
        transport = Transport(document, api, signing_key, mode=mode)
        transports.append(transport)
        host = host_parent / mode
        invoke = lambda: controller.execute_first_cell(request, host_state=host, grant=grant,
                                                       _test_transport=transport, _test_api=api)
        if mode == "harmless":
            result = positive("real_owned_supervisor_with_test_only_pass_payload", invoke)
            assert result["status"] == "failed" and result["grade"] is None and result["remote_terminal"] == "acknowledged"
            assert api.commits == ["admission", "output", "terminal"]
            assert owned._load(host / "owned-child.json")["tree_reaped"] is True
            cache = host / "observer"
            cache.mkdir()
            with retained._session(api) as (client, token, deadline):
                receipt = adapter.verify_terminal(client, api.repo, api.head, document, cache, token, deadline)
            assert receipt["observation_only"] is True and receipt["replay_authorized"] is False
            assert receipt["completion"]["accounting"] == "missing" and receipt["completion"]["receipt"] is None
            with pytest.raises(controller.RetentionControllerRefused, match="^first_cell_already_reserved_or_partial_no_replay$"):
                invoke()
            another_host = host_parent / "separate-host-root-no-second-claim"
            with monkeypatch.context() as no_second_clock:
                no_second_clock.setattr(CodexTaskDeadlineStore, "__init__", forbidden)
                with pytest.raises(adapter.RetentionCIRefused,
                                   match="^retention_claim_unresolved:retention_control_history_mismatch$"):
                    controller.execute_first_cell(request, host_state=another_host, grant=grant,
                                                   _test_transport=transport, _test_api=api)
            assert not (another_host / "deadline").exists() and api.commits == ["admission", "output", "terminal"]
        elif mode == "cleanup":
            with pytest.raises(owned.OwnedChildCleanupRefused, match="^owned_child_cleanup_unconfirmed$"):
                invoke()
            assert api.commits == ["admission"] and not (host / "remote-terminal-reserved.json").exists()
            with pytest.raises(owned.OwnedChildCleanupRefused, match="^owned_child_cleanup_unconfirmed$"):
                invoke()
        elif mode == "start_unknown":
            with pytest.raises(OSError, match="^synthetic_start_ack_unknown$"):
                invoke()
            assert api.commits == ["admission"] and not (host / "remote-terminal-reserved.json").exists()
            with pytest.raises(owned.OwnedChildCleanupRefused, match="^owned_child_cleanup_unconfirmed$"):
                invoke()
        else:
            with pytest.raises(adapter.RetentionCIRefused, match="^retention_terminal_unresolved:"):
                invoke()
            assert api.commits == ["admission", "output"] + (["terminal"] if mode == "terminal_unknown" else [])
            assert retained._read(host / "remote-terminal-receipt.json")["outcome"] == "unresolved"
            with pytest.raises(controller.RetentionControllerRefused, match="^first_cell_already_reserved_or_partial_no_replay$"):
                invoke()
            if mode == "terminal_unknown":
                cache = host / "separate-terminal-observer"
                cache.mkdir()
                with retained._session(api) as (client, token, deadline):
                    confirmed = adapter.verify_terminal(client, api.repo, api.head, document, cache, token, deadline)
                assert confirmed["replay_authorized"] is False
        assert len(transport.children) == 1 and all(api.trees[revision] == tree for revision, tree in old_trees.items())
        # Reopening the SAME real deadline preserves the first admission clock.
        transport.clock.now += 25
        store = controller._deadline(host, controller._context(request), controller.verify_staged_runtime(request), transport)
        try:
            assert store.for_task(registration.TASK4).remaining_seconds() == 10775
        finally:
            store.close()
        # The old terminal is no longer the CAS HEAD's writer. This is the actual
        # frozen predecessor-history refusal, not a mocked lock or validator.
        cache = host / "old-terminal-fence"
        cache.mkdir()
        with retained._session(api) as (client, token, deadline):
            with pytest.raises(output.OutputPublicationRefused, match="^retention_control_history_mismatch$"):
                retained._terminal(client, api.repo, api.head, observation["plan"], observation["plan"]["cells"][-1],
                                   observation["inputs"], cache, token, deadline)
        observed.append(mode)

    with pytest.raises(old_ci.CICellRefused, match="^registered_ci_campaign_required$"):
        old_ci.compile_ci_cell(registration.CAMPAIGN, controller.FIRST_CELL_ID, source)
    with pytest.raises(output.OutputPublicationRefused, match="^retained_epoch_mismatch$"):
        retained._binding({**registration.compile_plan(), "run_id": registration.CAMPAIGN},
                          controller._adapted_cell(registration.compile_plan()["cells"][0]), {})
    _assert_retention_execution_workflow_contract()
    assert not forbidden_calls
    assert time.sleep is guarded_sleep
    assert {binding["kind"] for binding in allowed_children.values()} == {
        "git", "historical_observe", "historical_materialize", "owned_supervisor"}
    assert all(process.returncode is not None for process in allowed_children)
    capsys.readouterr()
    print(json.dumps({"original_input_roles_sha256": document["input_roles_sha256"],
        "materialized_grader_source_sha256": document["grading"]["materialized_grader_source_sha256"],
        "adapter_source_sha256": document["source"]["adapter"]["sha256"],
        "request_sha256": owned._digest(document), "simulated_provider_cases": observed,
        "independent_original_serializations_equal": True, "signed_job_origin": "synthetic_rsa_raw_http_verified",
        "registered_local_child_kinds": sorted({binding["kind"] for binding in allowed_children.values()}),
        "stdlib_wait_sleep_kinds": sorted(allowed_waits),
        "real_payload": "test_owned_python_pass_only", "model_invocations": 0,
        "historical_observer_source": historical.SOURCE, "tested_source": source}, sort_keys=True))
