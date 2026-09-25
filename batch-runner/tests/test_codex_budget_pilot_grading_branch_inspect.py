"""Offline inspection only: real CLI/compiler/HTTP guards, synthetic HF replies.

Source admission is an explicit test double, not native host or live Git proof.
Sockets, mutation, payloads, setup state I/O and every grading phase are forbidden.
The consumed setup fixture is synthetic and must remain byte-for-byte unchanged.
"""

from __future__ import annotations

import copy
from datetime import datetime
import inspect
import json
import logging
import os
import signal
import socket
import subprocess
import time
from types import SimpleNamespace

import httpx
from huggingface_hub import HfApi, constants
from huggingface_hub.utils import _auth, _headers, _http
import pytest
import yaml

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading as connector
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import codex_ci_input_intake as intake

SOURCE = "1" * 40  # Synthetic source/CI authority, not the leader's seal.
OTHER_HEAD = "9" * 40
TOKEN = "hf_SYNTHETIC_BRANCH_INSPECTION"
RAW = "synthetic-secret https://private.invalid/signed?token=secret /private/raw-path"
SELECTOR = "pilot/branch-inspect"
FIELDS = {
    "campaign_id", "source_sha", "branch",
    "role", "repository_name_sha256", "outcome", "stage", "reason", "http_status",
    "branch_state", "head", "matches_bootstrap", "exact_identity_match", "private",
    "bootstrap_access_verified", "observed_at", "remote_mutation_possible",
    "judge_entry_requested", "inference_requested", "grade_success", "automatic_retry",
}


class SourceOnly(pilot.LocalTransport):
    def __init__(self):
        self.calls, self.fail = 0, False

    def require_source(self, plan, parent):
        assert plan["reviewed_source_sha"] == SOURCE and len(plan["cells"]) == 30
        assert parent is not None
        self.calls += 1
        if self.fail:
            raise ValueError(RAW)
        return {"tree_sha": "2" * 40, "common": "synthetic-source-capability"}


@pytest.fixture(scope="module")
def compilation():
    # Cache only a genuine deterministic compile. No original payloads are read.
    return pilot.compile_pilot(ci.CAMPAIGN, SOURCE)


@pytest.fixture
def case(tmp_path, monkeypatch, caplog, compilation):
    forbidden_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        raise AssertionError("branch inspection crossed an excluded boundary")

    root = tmp_path / "consumed-setup"
    root.mkdir(mode=0o700)
    history = {"branch-reserved.json": b'{"synthetic":"consumed"}\n',
               "branch-receipt.json": b'{"outcome":"unresolved","synthetic":true}\n'}
    for name, data in history.items():
        (root / name).write_bytes(data)
    for target, names in (
        (subprocess, ("Popen", "run", "check_call", "check_output")),
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (time, ("sleep",)),
        (_auth, ("get_token", "_get_token_from_file", "_get_token_from_environment", "_get_token_from_google_colab")),
        (_headers, ("get_token",)),
        (pilot, ("dispatch",)),
        (pilot.LocalTransport, ("require_execution", "inputs", "checkout", "child", "process")),
        (connector, ("setup", "prepare", "claim", "judge", "publish", "reconcile", "_root", "_record", "_remote_download_file")),
        (retained, ("_session", "_remote_download_file")),
        (output, ("prepare", "publish", "_write_no_clobber")),
        (intake, ("intake", "intake_hf_originals", "_hf_read")),
        (HfApi, ("create_branch", "delete_branch", "create_commit", "create_repo", "delete_repo", "whoami",
                 "get_paths_info", "list_repo_files", "list_repo_refs", "hf_hub_download", "upload_file", "upload_folder")),
    ):
        for name in names:
            monkeypatch.setattr(target, name, forbidden)
    original_compile = pilot.compile_pilot
    monkeypatch.setattr(pilot, "compile_pilot", lambda campaign, source:
                        copy.deepcopy(compilation) if (campaign, source) == (ci.CAMPAIGN, SOURCE)
                        else original_compile(campaign, source))
    for key, value in {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": ci.REPOSITORY, "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": SOURCE, "PILOT_WORKFLOW_SHA": SOURCE,
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "12345", "GITHUB_JOB": "pilot-live",
        "GITHUB_WORKFLOW_REF": ci.REPOSITORY + "/" + connector.WORKFLOW + "@refs/heads/main",
        "PILOT_GRADE_PAID_APPROVAL": "true", "PILOT_GRADE_DRY_RUN": "false",
        "GRADE_CONFIG": "default_v2_sol_max.yaml", "GRADE_FORCE": "false", "GRADE_TASKS_LIMIT": "0",
        "GRADE_TASKS": "", "GRADE_RESUME": "false", "GRADE_RESUME_CHUNK": "0",
        "GRADE_SHARD_COUNT": "1", "GRADE_SHARD_INDEX": "0", "GRADE_RUN_ORDINAL": "1",
        "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
        "HF_TOKEN": TOKEN, "HUGGING_FACE_HUB_TOKEN": "synthetic-ambient-hf", "GITHUB_TOKEN": "synthetic-ambient-github",
        "GITHUB_OUTPUT": str(tmp_path / "forbidden-workflow-output"),
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(constants, "HF_HUB_OFFLINE", True)
    repo = retained._target()
    state = SimpleNamespace(root=root, history=history, repo=repo, transport=SourceOnly(),
        requests=[], sdk_calls=[], replies={}, logs=caplog, forbidden=forbidden,
        cell=compilation[0]["order"][ci.FIRST_CELL_ORDINAL])
    for revision in (retained.BOOTSTRAP, connector.BRANCH):
        state.replies[revision] = {"status": 200, "error_code": None, "failure": None,
            "metadata": {"id": repo, "private": True, "sha": retained.BOOTSTRAP,
                         "siblings": [{"rfilename": RAW}], "raw_private": RAW}}
    real_repo_info = HfApi.repo_info

    def repo_info(api, **kwargs):
        valid = (kwargs["repo_id"] == repo and kwargs["repo_type"] == "dataset"
                 and kwargs["revision"] in state.replies and kwargs["token"] == TOKEN
                 and 0 < kwargs["timeout"] <= 20)
        if not valid:
            raise AssertionError("fixed explicit metadata arguments required")
        state.sdk_calls.append(kwargs["revision"])
        return real_repo_info(api, **kwargs)

    def request(transport, message):
        revision = message.url.path.rsplit("/", 1)[-1]
        valid = (message.method == "GET" and revision in state.replies
                 and str(message.url) == f"https://huggingface.co/api/datasets/{repo}/revision/{revision}"
                 and not message.content and message.headers.get("authorization") == "Bearer " + TOKEN)
        if not valid:
            raise AssertionError("noncanonical request reached the HTTP boundary")
        state.requests.append(revision)
        assert all(0 < value <= 20 for value in message.extensions["timeout"].values())
        assert 0 < signal.getitimer(signal.ITIMER_REAL)[0] <= 20
        assert constants.HF_HUB_OFFLINE is False and os.environ["HF_HUB_OFFLINE"] == "0"
        assert os.environ["HF_DATASETS_OFFLINE"] == "1"
        assert not {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN"}.intersection(os.environ)
        reply = state.replies[revision]
        if reply["failure"] == "connect":
            raise httpx.ConnectError(RAW)
        if reply["failure"] == "timeout":
            signal.raise_signal(signal.SIGALRM)
        if reply["failure"] == "json":
            return httpx.Response(200, stream=httpx.ByteStream(RAW.encode()))
        if reply["failure"] == "size":
            return httpx.Response(200, stream=httpx.ByteStream(b"x" * (output.MAX_RECORD_BYTES + 1)))
        headers = {"location": "https://private.invalid/?token=secret"}
        if reply["error_code"] is not None:
            headers["X-Error-Code"] = reply["error_code"]
        return httpx.Response(reply["status"], json=reply["metadata"], headers=headers)

    monkeypatch.setattr(HfApi, "repo_info", repo_info)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", request)
    yield state
    assert forbidden_calls == []  # Caught refusals may not hide forbidden calls.
    assert {path.name: path.read_bytes() for path in root.iterdir()} == history
    assert not (tmp_path / "forbidden-workflow-output").exists()


def invoke(case, capsys, phase="inspect", *, selector=SELECTOR, terminal=""):
    old_env = dict(os.environ)
    old_factory, old_logging = _http._GLOBAL_CLIENT_FACTORY, logging.root.manager.disable
    argv = ["--selector", selector, "--reviewed-source-sha", SOURCE,
            "--terminal-revision", terminal, "--root", str(case.root)]
    code = connector.main(argv + ([] if phase is None else ["--phase", phase]), _test_transport=case.transport)
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert all(secret not in text + case.logs.text for secret in (TOKEN, RAW, case.repo, str(case.root)))
    assert len(text.encode()) <= 2048 and bool(captured.out) != bool(captured.err)
    assert dict(os.environ) == old_env
    assert _http._GLOBAL_CLIENT_FACTORY is old_factory and logging.root.manager.disable == old_logging
    assert constants.HF_HUB_OFFLINE is True and signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    record = json.loads(text)
    if selector == SELECTOR:
        assert set(record) == FIELDS and record["repository_name_sha256"] == retained.TARGET_SHA256
        assert record["role"] == "fixed_private_pilot_grading_branch_inspection"
        assert all(record[key] is False for key in ("remote_mutation_possible", "judge_entry_requested",
            "inference_requested", "grade_success", "automatic_retry"))
        if record["observed_at"] is not None:
            assert datetime.fromisoformat(record["observed_at"]).utcoffset().total_seconds() == 0
    return code, record


def test_branch_inspect_plan_never_looks_up_tokens_or_calls_source_or_network(case, monkeypatch, capsys):
    class NoToken(dict):
        def get(self, key, *args):
            if key in {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN"}:
                case.forbidden()
            return super().get(key, *args)

    monkeypatch.setattr(os, "environ", NoToken(os.environ))
    monkeypatch.setattr(output, "_hf_client", case.forbidden)
    code, record = invoke(case, capsys, None)
    assert code == 0 and record["outcome"] == "plan_only" and record["stage"] == "plan"
    assert record["observed_at"] is record["http_status"] is record["head"] is None
    assert case.transport.calls == 0 and case.requests == case.sdk_calls == []


def test_branch_inspect_present_at_bootstrap_is_only_a_separate_observation(case, monkeypatch, capsys):
    timers, original_timer = [], signal.setitimer

    def timer(which, seconds):
        timers.append(seconds)
        return original_timer(which, seconds)

    monkeypatch.setattr(signal, "setitimer", timer)
    code, record = invoke(case, capsys)
    assert code == 0 and record["outcome"] == "observed" and record["branch_state"] == "present"
    assert record["head"] == retained.BOOTSTRAP and record["matches_bootstrap"] is True
    assert record["exact_identity_match"] is record["private"] is record["bootstrap_access_verified"] is True
    assert record["http_status"] == 200 and record["stage"] == "branch_metadata" and record["reason"] is None
    assert case.sdk_calls == case.requests == [retained.BOOTSTRAP, connector.BRANCH]
    assert case.transport.calls == 1
    assert timers == [20, 0]  # One shared deadline, not a new budget per GET.


def test_branch_404_requires_verified_bootstrap_and_exact_revision_discriminator(case, capsys):
    case.replies[connector.BRANCH].update(status=404, error_code="RevisionNotFound")
    code, record = invoke(case, capsys)
    assert code == 0 and record["outcome"] == "observed" and record["branch_state"] == "absent"
    assert record["bootstrap_access_verified"] is True and record["http_status"] == 404
    assert record["stage"] == "branch_metadata" and record["reason"] == "grading_branch_absent"
    assert record["head"] is record["matches_bootstrap"] is None
    assert case.requests == [retained.BOOTSTRAP, connector.BRANCH]


@pytest.mark.parametrize("discriminator", [None, "RepoNotFound", "RevisionNotFound-extra"])
def test_ambiguous_branch_404_is_unknown_not_absence(case, capsys, discriminator):
    case.replies[connector.BRANCH].update(status=404, error_code=discriminator)
    code, record = invoke(case, capsys)
    assert code == 2 and record["outcome"] == "refused" and record["branch_state"] == "inaccessible_or_unknown"
    assert record["bootstrap_access_verified"] is True and record["http_status"] == 404
    assert record["reason"] == "hf_http_failed" and record["head"] is None and len(case.requests) == 2


@pytest.mark.parametrize("status", [401, 403, 404, 503])
def test_bootstrap_http_failure_never_reads_or_classifies_branch_absence(case, capsys, status):
    case.replies[retained.BOOTSTRAP].update(status=status, error_code="RevisionNotFound")
    code, record = invoke(case, capsys)
    assert code == 2 and record["branch_state"] == "inaccessible_or_unknown"
    assert record["bootstrap_access_verified"] is False and record["http_status"] == status
    assert record["stage"] == "bootstrap_metadata" and record["head"] is None
    assert case.requests == [retained.BOOTSTRAP]


@pytest.mark.parametrize("revision", [retained.BOOTSTRAP, connector.BRANCH], ids=["bootstrap", "branch"])
@pytest.mark.parametrize("field,value,reason", [
    ("id", "synthetic-foreign/repository", "grading_branch_identity_mismatch"),
    ("private", False, "private_grading_branch_required"),
    ("sha", OTHER_HEAD, None),
])
def test_private_identity_or_seed_drift_is_observed_but_blocked(case, capsys, revision, field, value, reason):
    case.replies[revision]["metadata"][field] = value
    code, record = invoke(case, capsys)
    assert code == 2 and record["outcome"] == "blocked_drift" and record["http_status"] == 200
    assert len(case.requests) == (1 if revision == retained.BOOTSTRAP else 2)
    if reason is None:
        reason = "recorded_bootstrap_required" if revision == retained.BOOTSTRAP else "grading_branch_seed_mismatch"
    assert record["reason"] == reason
    if revision == connector.BRANCH and field == "sha":
        assert record["branch_state"] == "present" and record["head"] == OTHER_HEAD
        assert record["matches_bootstrap"] is False
    else:
        assert record["branch_state"] == "inaccessible_or_unknown" and record["head"] is None


def test_missing_explicit_token_never_discovers_ambient_credentials(case, monkeypatch, capsys):
    monkeypatch.delenv("HF_TOKEN")
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "explicit_hf_token_required"
    assert record["http_status"] is None and record["stage"] == "inspection_preflight" and case.requests == []


@pytest.mark.parametrize("revision,failure,status,reason", [
    (retained.BOOTSTRAP, "connect", None, "hf_transport_failed"),
    (connector.BRANCH, "connect", None, "hf_transport_failed"),
    (connector.BRANCH, "timeout", None, "grading_branch_inspection_timeout"),
    (connector.BRANCH, "json", 200, "grading_branch_inspection_failed"),
    (retained.BOOTSTRAP, "size", 200, "hf_response_bytes_exceeded"),
])
def test_unavailable_or_invalid_metadata_has_only_received_status(case, monkeypatch, capsys, revision, failure, status, reason):
    case.replies[revision]["failure"] = failure
    if failure == "size":
        monkeypatch.setattr(output, "MAX_RECORD_BYTES", 64)
    code, record = invoke(case, capsys)
    assert code == 2 and record["branch_state"] == "inaccessible_or_unknown"
    assert record["reason"] == reason and record["http_status"] == status
    assert len(case.requests) == (1 if revision == retained.BOOTSTRAP else 2)


def test_redirect_is_terminal_without_following_its_location(case, capsys):
    case.replies[connector.BRANCH]["status"] = 307
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "hf_metadata_redirect_refused" and record["http_status"] == 307
    assert case.requests == [retained.BOOTSTRAP, connector.BRANCH]


def test_exact_bodyless_authenticated_get_guard_blocks_mutation_and_other_routes(case, monkeypatch, capsys):
    for damage in ("POST", "PUT", "DELETE", "body", "revision", "host", "query", "bearer"):
        def unexpected(api, **kwargs):
            url = f"https://huggingface.co/api/datasets/{case.repo}/revision/{retained.BOOTSTRAP}"
            if damage == "revision":
                url = url.removesuffix(retained.BOOTSTRAP) + "main"
            elif damage == "host":
                url = url.replace("huggingface.co", "foreign.invalid")
            elif damage == "query":
                url += "?secret=synthetic"
            return _http.get_session().request(damage if damage in {"POST", "PUT", "DELETE"} else "GET", url,
                content=b"synthetic-body" if damage == "body" else b"",
                headers={"authorization": "Bearer " + ("synthetic-other" if damage == "bearer" else TOKEN)})

        monkeypatch.setattr(HfApi, "repo_info", unexpected)
        code, record = invoke(case, capsys)
        assert code == 2 and record["reason"] == "hf_metadata_request_refused"
        assert record["http_status"] is None and case.requests == []


def test_one_get_limit_survives_sdk_client_recreation(case, monkeypatch, capsys):
    original = HfApi.repo_info

    def repeated(api, **kwargs):
        original(api, **kwargs)
        _http.set_client_factory(_http._GLOBAL_CLIENT_FACTORY)
        return original(api, **kwargs)

    monkeypatch.setattr(HfApi, "repo_info", repeated)
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "hf_metadata_request_refused" and record["http_status"] == 200
    assert record["bootstrap_access_verified"] is False and case.requests == [retained.BOOTSTRAP]


def test_revision_components_and_default_single_main_mode_are_not_broadened(case):
    assert inspect.signature(output._hf_client).parameters["metadata_revision"].default == "main"
    for revision in ("../main", "a/b", "%2Fmain", "main?x=1", "main#x", "*", "main\n", "main\\x"):
        with output._time_bound(20) as deadline, intake._hf_environment(online=True):
            with pytest.raises(output.OutputPublicationRefused, match="hf_metadata_request_refused"):
                with output._hf_client(TOKEN, deadline, metadata_repo=case.repo, metadata_revision=revision, observation={}):
                    pytest.fail("unsafe revision admitted")
    assert case.requests == []


def test_selector_phase_cross_use_and_terminal_override_refuse_before_source_or_token(case, monkeypatch, capsys):
    monkeypatch.setattr(output, "_hf_client", case.forbidden)
    for selector, phases in ((SELECTOR, ("setup", "prepare", "claim", "judge", "publish", "reconcile")),
                             ("pilot/branch-setup", ("inspect",)),
                             ("pilot/" + case.cell, ("inspect", "setup"))):
        for phase in phases:
            code, record = invoke(case, capsys, phase, selector=selector)
            assert code == 2 and record["reason"] == "pilot_grade_mode_conflict"
    code, record = invoke(case, capsys, terminal=OTHER_HEAD)
    assert code == 2 and record["reason"] == "branch_inspection_has_no_inference_revision"
    assert case.transport.calls == 0 and case.requests == []


def test_source_context_and_fixed_target_fail_closed_before_metadata(case, monkeypatch, capsys):
    case.transport.fail = True
    code, record = invoke(case, capsys)
    assert code == 2 and record["stage"] == "source_preflight" and record["reason"] == "grading_source_preflight_refused"
    case.transport.fail = False
    with monkeypatch.context() as patch:
        patch.setenv("GITHUB_RUN_ATTEMPT", "2")
        code, record = invoke(case, capsys)
        assert code == 2 and record["reason"] == "explicit_first_attempt_reviewed_grading_context_required"
    real_load = pilot.load_plan
    monkeypatch.setattr(pilot, "load_plan", lambda path: {"data": {"source": "synthetic-foreign/repo"}}
                        if path == pilot.ROOT / pilot.CODEX_TEMPLATE else real_load(path))
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "registered_output_target_mismatch" and case.requests == []


def test_workflow_inspection_is_isolated_without_new_inputs_or_paid_routes():
    workflow = yaml.safe_load((pilot.ROOT / connector.WORKFLOW).read_text())
    inputs = (workflow.get("on") or workflow[True])["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"experiment_yaml", "grading_config", "inference_revision", "force", "tasks_limit", "tasks",
                          "dry_run", "paid_approval", "resume", "resume_chunk", "shard_count", "shard_index", "run_ordinal"}
    jobs = workflow["jobs"]
    for name in ("validate-request", "approve-paid", "grade-dry-run", "grade", "verify-published"):
        assert "!startsWith(inputs.experiment_yaml, 'pilot/')" in jobs[name]["if"]
    plan, live = jobs["pilot-plan"], jobs["pilot-live"]
    assert "inputs.dry_run == true" in plan["if"] and plan["permissions"] == {"contents": "read"}
    assert "inputs.paid_approval == true" in live["if"] and live["environment"]["name"] == "grading"
    assert live["permissions"] == {"contents": "read", "id-token": "write"} and live["timeout-minutes"] == 300
    assert "HF_TOKEN" not in live["env"] and "HF_TOKEN" not in plan["env"]
    token_steps = [step for step in live["steps"] if "HF_TOKEN" in step.get("env", {})]
    phases = {phase: next(step for step in token_steps if "--phase " + phase in step["run"])
              for phase in ("setup", "inspect", "prepare", "claim", "publish")}
    assert len(token_steps) == len(phases) == 5
    assert phases["setup"]["if"] == ("inputs.experiment_yaml == 'pilot/branch-setup' || "
                                     "inputs.experiment_yaml == 'pilot/inference-branch-setup'")
    assert phases["inspect"]["if"] == ("inputs.experiment_yaml == 'pilot/branch-inspect' || "
                                       "inputs.experiment_yaml == 'pilot/inference-branch-inspect'")
    assert phases["inspect"]["timeout-minutes"] == 2 and "--terminal-revision" in phases["inspect"]["run"]
    assert "inputs.experiment_yaml != 'pilot/branch-inspect'" in phases["prepare"]["if"]
    renderer = next(step for step in live["steps"] if "preflight_grading_renderer.py" in step.get("run", ""))
    assert "inputs.experiment_yaml != 'pilot/branch-inspect'" in renderer["if"]
    for step in live["steps"]:
        if ("azure" in step.get("run", "").lower() or "azure/login" in step.get("uses", "")
                or step.get("id") in {"pilot_claim", "pilot_judge"}):
            assert "steps.pilot_input.outputs.judge_ready == 'true'" in step["if"]
    assert "steps.pilot_claim.outcome == 'success'" in phases["publish"]["if"]
    assert "steps.pilot_judge.outcome != 'skipped'" in phases["publish"]["if"]
    for job in (plan, live):
        assert not any("upload-artifact" in step.get("uses", "") for step in job["steps"])
    validation = next(step for step in live["steps"] if step.get("name") == "Validate the exact selected pilot route")
    assert all(fragment in validation["run"] for fragment in (
        'test "$GITHUB_SHA" = "$PILOT_WORKFLOW_SHA"', 'test "$GITHUB_REF" = refs/heads/main',
        'test "$GITHUB_RUN_ATTEMPT" = 1'))
    assert ci.PUBLIC_FIXED["grading_launched"] is False
