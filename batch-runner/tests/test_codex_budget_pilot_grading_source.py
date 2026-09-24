"""Offline source-entry regression: real temporary Git, no HF or paid work.

Git's test-only different-owner switch exercises its actual ownership check;
no filesystem ownership changes or simulated Git answers are used. Branch
mutation below is an in-memory fake, not reconciliation of the failed CI run.
"""

from contextlib import contextmanager
import json
import subprocess
import time
from types import SimpleNamespace

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading as connector
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import gpt54_comparison_preflight as preflight
import gpt54_disposable_checkout as checkout
from gpt54_run_config_bundle import MANIFEST_PATH
from .test_gpt54_disposable_checkout import (
    _GIT_ENV, _allow_only_temporary_git, _commit_fixture, _fixture_git,
)


RAW_ERROR = "synthetic-secret https://private.invalid/signed?token=synthetic /private/raw-path"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    from huggingface_hub import HfApi
    from huggingface_hub.utils import _auth, _headers
    from core import codex_runtime_config

    def forbidden(*args, **kwargs):
        pytest.fail("source-entry regression crossed an auth/network/runtime boundary")

    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN", "GITHUB_OUTPUT"):
        monkeypatch.delenv(name, raising=False)
    for name in ("HF_HUB_OFFLINE", "HF_DATASETS_OFFLINE", "HF_HUB_DISABLE_IMPLICIT_TOKEN"):
        monkeypatch.setenv(name, "1")
    monkeypatch.setenv("GITHUB_ACTIONS", "false")
    for name in ("repo_info", "create_branch", "create_commit", "create_repo", "hf_hub_download", "whoami"):
        monkeypatch.setattr(HfApi, name, forbidden)
    for name in ("get_token", "_get_token_from_file", "_get_token_from_environment", "_get_token_from_google_colab"):
        monkeypatch.setattr(_auth, name, forbidden)
    monkeypatch.setattr(_headers, "get_token", forbidden)
    monkeypatch.setattr(retained, "_session", forbidden)
    monkeypatch.setattr(pilot, "dispatch", forbidden)
    monkeypatch.setattr(pilot.LocalTransport, "require_execution", forbidden)
    monkeypatch.setattr(codex_runtime_config, "require_pinned_runtime", forbidden)
    for name in ("prepare", "claim", "judge", "publish", "reconcile"):
        monkeypatch.setattr(connector, name, forbidden)


@pytest.fixture
def source(tmp_path, monkeypatch):
    # Reuse the existing bounded/process-isolated temporary-Git guard. Inject
    # the real Git ownership test switch only AFTER that guard checks the exact
    # production environment. Production itself must never inherit the switch.
    real_popen = subprocess.Popen
    ownership_commands = []

    def different_owner(command, *args, **kwargs):
        if kwargs.get("env") == _GIT_ENV:
            ownership_commands.append(True)
            kwargs["env"] = {**_GIT_ENV, "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"}
        return real_popen(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", different_owner)
    forbidden, calls = _allow_only_temporary_git(monkeypatch, tmp_path)
    repository = tmp_path / "source"
    repository.mkdir()
    manifest = preflight.load_plan()
    parent_registration = pilot.REGISTRATION.relative_to(pilot.ROOT)
    ci_registration = ci.REGISTRATION.relative_to(pilot.ROOT)
    # Only tracked source metadata/code, never original parquet/reference data.
    # Include both genuine registrations in the clean synthetic commit.
    for role in (*manifest["source_pins"], MANIFEST_PATH, parent_registration, ci_registration):
        destination = repository / role
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((preflight.ROOT / role).read_bytes())
    _fixture_git(repository, "init", "--quiet", "--initial-branch=fixture-main", "--object-format=sha1", "--template=")
    sha = _commit_fixture(repository, "Synthetic reviewed source fixture")
    monkeypatch.setattr(pilot, "ROOT", repository)
    monkeypatch.setattr(pilot, "REGISTRATION", repository / parent_registration)
    monkeypatch.setattr(ci, "REGISTRATION", repository / ci_registration)
    monkeypatch.setattr(checkout, "TRUSTED_ROOT", repository)
    plan, parent, _ = pilot.compile_pilot(ci.CAMPAIGN, sha)

    def ordinary_git(global_config):
        # One fixed local diagnostic command; return only redacted facts.
        process = real_popen(
            ["/usr/bin/git", "-C", str(repository), "rev-parse", "--show-toplevel"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**_GIT_ENV, "GIT_CONFIG_GLOBAL": str(global_config),
                 "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"},
        )
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            pytest.fail("bounded synthetic Git diagnostic timed out")
        return process.returncode, b"detected dubious ownership" in stderr, stdout == str(repository).encode() + b"\n"

    yield SimpleNamespace(repository=repository, sha=sha, plan=plan, parent=parent,
                          calls=calls, ownership_commands=ownership_commands, ordinary_git=ordinary_git)
    assert forbidden == []


def test_real_git_global_trust_is_ignored_but_exact_command_trust_works(source, tmp_path, monkeypatch, record_property):
    record_property("ownership_boundary", "real_git_GIT_TEST_ASSUME_DIFFERENT_OWNER_no_chown")
    global_config = tmp_path / "isolated-global-config"
    global_config.write_text('[safe]\n\tdirectory = "' + str(source.repository) + '"\n')
    assert source.ordinary_git(global_config) == (0, False, True)
    assert source.ordinary_git("/dev/null") == (128, True, False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    assert checkout._repository(source.repository) == (source.repository, source.repository / ".git")

    foreign = tmp_path / "foreign"
    foreign.mkdir()
    _fixture_git(foreign, "init", "--quiet", "--initial-branch=fixture-main", "--template=")
    alias = tmp_path / "aliased-source"
    alias.symlink_to(source.repository, target_is_directory=True)
    for unrelated in (foreign, tmp_path / "unavailable-external-source", alias):
        monkeypatch.setattr(checkout, "TRUSTED_ROOT", unrelated)
        # Existing, missing and aliased roots grant no foreign ownership trust.
        # The caller's exact global allowance still cannot affect hardened Git.
        with pytest.raises(checkout.DisposableCheckoutRefused, match=r"local Git rev-parse refused \(128\)"):
            checkout._repository(source.repository)
    assert source.ownership_commands


@pytest.mark.parametrize("shallow", [False, True], ids=["normal", "depth-one"])
def test_real_reviewed_clean_source_passes_without_runtime_or_ancestor_history(source, monkeypatch, shallow):
    if shallow:
        (source.repository / ".git/shallow").write_text(source.sha + "\n")
        assert checkout._git(source.repository, "rev-parse", "--is-shallow-repository").stdout == b"true\n"
    original_config = (source.repository / ".git/config").read_bytes()
    for key, value in {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
                       "GIT_CONFIG_VALUE_0": "*", "GIT_DIR": "/synthetic-foreign",
                       "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"}.items():
        monkeypatch.setenv(key, value)
    observed = pilot.LocalTransport().require_source(source.plan, source.parent)
    assert output._hash(observed["tree_sha"], 40)
    assert observed["common"] == str(source.repository / ".git")
    assert (source.repository / ".git/config").read_bytes() == original_config
    assert source.ownership_commands
    assert {args[0] for _, args in source.calls} <= {"rev-parse", "config", "status", "cat-file", "ls-tree"}


@pytest.mark.parametrize("damage", ["tracked_dirty", "untracked", "wrong_source", "pin_mismatch", "manifest_mismatch", "tracked_symlink"])
def test_real_source_validation_remains_fail_closed(source, damage):
    requested = source.sha
    helper = source.repository / "batch-runner/gpt54_disposable_checkout.py"
    if damage in {"tracked_dirty", "pin_mismatch"}:
        helper.write_bytes(helper.read_bytes() + b"\n# synthetic drift\n")
    elif damage == "untracked":
        (source.repository / "unreviewed.txt").write_text("synthetic")
    elif damage == "wrong_source":
        requested = "f" * 40
    elif damage == "manifest_mismatch":
        manifest = source.repository / MANIFEST_PATH
        manifest.write_bytes(manifest.read_bytes() + b"\nunreviewed_field: true\n")
    else:
        (source.repository / "unreviewed-link").symlink_to("synthetic-absent")
    if damage in {"pin_mismatch", "manifest_mismatch", "tracked_symlink"}:
        requested = _commit_fixture(source.repository, "Synthetic invalid reviewed source")
    plan, parent, _ = pilot.compile_pilot(ci.CAMPAIGN, requested)
    with pytest.raises(ValueError):
        pilot.LocalTransport().require_source(plan, parent)


@pytest.mark.parametrize("key", ["filter.synthetic.clean", "include.path", "remote.synthetic.promisor", "core.alternateRefsCommand"])
def test_real_source_refuses_unsafe_local_configuration_before_status(source, key):
    _fixture_git(source.repository, "config", key, "true" if key.endswith(".promisor") else "synthetic-unsupported")
    with pytest.raises(checkout.DisposableCheckoutRefused, match="filters, includes or partial-clone"):
        pilot.LocalTransport().require_source(source.plan, source.parent)
    assert not any(args[0] == "status" for _, args in source.calls)


@pytest.mark.parametrize("kind", ["symlink", "traversal", "wildcard", "newline", "control"])
def test_unsafe_trusted_root_never_reaches_git(source, tmp_path, monkeypatch, kind):
    if kind == "symlink":
        unsafe = tmp_path / "linked-source"
        unsafe.symlink_to(source.repository, target_is_directory=True)
    elif kind == "traversal":
        unsafe = source.repository / ".." / "source"
    else:
        unsafe = tmp_path / {"wildcard": "wild*card", "newline": "line\nbreak", "control": "control\x7f"}[kind]
        unsafe.mkdir()
    monkeypatch.setattr(checkout, "TRUSTED_ROOT", unsafe)
    before = len(source.calls)
    with pytest.raises(ValueError):
        # Test the selected unsafe path, not an unrelated compiler directory.
        checkout._repository(unsafe)
    assert len(source.calls) == before


def _authority(monkeypatch, source):
    values = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": ci.REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": source.sha, "PILOT_WORKFLOW_SHA": source.sha, "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": ci.REPOSITORY + "/" + connector.WORKFLOW + "@refs/heads/main",
        "GITHUB_RUN_ID": "123456", "GITHUB_JOB": "pilot-live",
        "PILOT_GRADE_PAID_APPROVAL": "true", "PILOT_GRADE_DRY_RUN": "false",
        "GRADE_CONFIG": "default_v2_sol_max.yaml", "GRADE_FORCE": "false", "GRADE_TASKS_LIMIT": "0",
        "GRADE_TASKS": "", "GRADE_RESUME": "false", "GRADE_RESUME_CHUNK": "0",
        "GRADE_SHARD_COUNT": "1", "GRADE_SHARD_INDEX": "0", "GRADE_RUN_ORDINAL": "1",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def _invoke(source, root, capsys, phase="setup"):
    code = connector.main(["--selector", "pilot/branch-setup", "--reviewed-source-sha", source.sha,
                           "--root", str(root), "--phase", phase])
    captured = capsys.readouterr()
    text = captured.out + captured.err
    for private in (str(source.repository), str(root), RAW_ERROR, "synthetic-secret", "https://", "Traceback", "dubious ownership"):
        assert private not in text, "CLI leaked a private/raw diagnostic"
    return code, json.loads(text)


def _refusal(value, stage, reason, possible):
    assert value == {"role": "fixed_private_pilot_grading", "outcome": "refused",
                     "stage": stage, "reason": reason, "http_status": None,
                     "remote_mutation_possible": possible, "inference_requested": False,
                     "grade_success": False, "automatic_retry": False}


def test_cli_plan_does_not_run_source_preflight_or_setup(source, tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("plan reached a live source/setup gate")
    monkeypatch.setattr(pilot.LocalTransport, "require_source", forbidden)
    monkeypatch.setattr(connector, "setup", forbidden)
    root = tmp_path / "plan-only"
    code, value = _invoke(source, root, capsys, "plan")
    assert code == 0 and value["outcome"] == "plan_only" and not value["judge_entry_requested"]
    assert not root.exists() and not source.calls


@pytest.mark.parametrize("cause", ["dirty", "foreign_trust", "arbitrary_exception"])
def test_cli_source_refusal_has_closed_stage_before_local_or_remote_mutation(source, tmp_path, monkeypatch, capsys, cause):
    if cause == "dirty":
        (source.repository / "unreviewed.txt").write_text("synthetic")
    elif cause == "foreign_trust":
        foreign = tmp_path / "different-authorized-root"
        foreign.mkdir()
        monkeypatch.setattr(checkout, "TRUSTED_ROOT", foreign)
    else:
        def fail(*args):
            raise RuntimeError(RAW_ERROR)
        monkeypatch.setattr(pilot.LocalTransport, "require_source", fail)
    root = tmp_path / "no-setup"
    code, value = _invoke(source, root, capsys)
    assert code == 2 and not root.exists()
    _refusal(value, "source_preflight", "grading_source_preflight_refused", False)


@pytest.mark.parametrize("cause", ["existing_root", "lock_entry"])
def test_cli_root_refusal_is_before_session_and_retains_partial_local_state(source, tmp_path, monkeypatch, capsys, cause):
    _authority(monkeypatch, source)
    root = tmp_path / "setup-root"
    if cause == "existing_root":
        root.mkdir(mode=0o700)
    else:
        @contextmanager
        def fail_lock(*args):
            raise OSError(RAW_ERROR)
            yield
        monkeypatch.setattr(connector, "_lock", fail_lock)
    code, value = _invoke(source, root, capsys)
    assert code == 2 and root.is_dir()
    _refusal(value, "branch_root", "grading_root_refused", False)
    if cause == "lock_entry":
        assert (root / "lock").is_file()


@pytest.mark.parametrize("lost_response", [False, True], ids=["acknowledged-fake-create", "lost-fake-response"])
def test_cli_receipt_failure_preserves_reservation_and_unknown_mutation_without_replay(source, tmp_path, monkeypatch, capsys, lost_response):
    _authority(monkeypatch, source)
    repo, token = retained._target(), "synthetic-not-a-credential"
    calls, created = [], []

    class FakeBranch:
        def repo_info(self, **kwargs):
            matches = kwargs["repo_id"] == repo and kwargs["token"] == token
            assert matches and kwargs["repo_type"] == "dataset"
            assert 0 < kwargs["timeout"] <= output.REQUEST_SECONDS
            revision = kwargs["revision"]
            assert revision in {retained.BOOTSTRAP, connector.BRANCH}
            calls.append(("metadata", revision))
            if revision == connector.BRANCH and not created:
                raise output.OutputPublicationRefused("hf_revision_not_found", 404)
            return SimpleNamespace(id=repo, private=True, sha=retained.BOOTSTRAP)

        def create_branch(self, **kwargs):
            matches = kwargs["repo_id"] == repo and kwargs["token"] == token
            assert matches and kwargs["repo_type"] == "dataset"
            assert kwargs["branch"] == connector.BRANCH and kwargs["revision"] == retained.BOOTSTRAP
            assert kwargs["exist_ok"] is False and not created
            calls.append(("create", connector.BRANCH))
            created.append(True)
            if lost_response:
                raise OSError(RAW_ERROR)

    @contextmanager
    def fake_session(*args, **kwargs):
        assert kwargs["_branch_setup"]["setup_repo"] == repo
        assert kwargs["_branch_setup"]["setup_branch"] == connector.BRANCH
        yield FakeBranch(), token, time.monotonic() + 20

    record = connector._record

    def fail_receipt(path, value):
        if path.name == "branch-receipt.json":
            raise OSError(RAW_ERROR)
        return record(path, value)

    monkeypatch.setattr(retained, "_session", fake_session)
    monkeypatch.setattr(connector, "_record", fail_receipt)
    root = tmp_path / "receipt-failure"
    code, value = _invoke(source, root, capsys)
    assert code == 2 and created == [True]
    _refusal(value, "branch_receipt", "grading_receipt_refused", True)
    reservation = (root / "branch-reserved.json").read_bytes()
    assert json.loads(reservation)["source_sha"] == source.sha
    assert not (root / "branch-receipt.json").exists()
    before = list(calls)
    code, value = _invoke(source, root, capsys)
    assert code == 2 and calls == before and created == [True]
    _refusal(value, "branch_root", "grading_root_refused", False)
    assert (root / "branch-reserved.json").read_bytes() == reservation


@pytest.mark.parametrize("typed", [False, True], ids=["unknown-contract", "existing-typed-http"])
def test_cli_unrelated_error_does_not_invent_a_stage_or_mutation_history(source, tmp_path, monkeypatch, capsys, typed):
    def fail():
        if typed:
            raise output.OutputPublicationRefused("hf_http_failed", 503)
        raise ValueError(RAW_ERROR)
    monkeypatch.setattr(connector, "_workflow_inputs", fail)
    code, value = _invoke(source, tmp_path / "untouched", capsys)
    assert code == 2
    assert value["stage"] is None and value["remote_mutation_possible"] is None
    assert value["http_status"] == (503 if typed else None)
    assert value["reason"] == ("hf_http_failed" if typed else "grading_contract_refused")
    assert value["grade_success"] is False and value["automatic_retry"] is False
