"""One free selector: reviewed local Git, exact bundles, retained quarantine."""

from __future__ import annotations

import json
import shlex
import subprocess
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import gpt54_codex_input_capture as writer
import gpt54_comparison_preflight as preflight
import gpt54_disposable_checkout as preparer
import gpt54_run_config_bundle as config_bundle
import gpt54_run_input_bundle as input_bundle
from .test_gpt54_prepared_input_attestation import (
    _bundle_fixture, _identity, _json, _tree_snapshot,
)
from .test_gpt54_run_config_bundle import _guards
from .test_gpt54_run_input_bundle import _input_bundle_seed


_GIT_SETTINGS = (
    "core.hooksPath=/dev/null", "core.fsmonitor=false",
    "core.attributesFile=/dev/null", "core.autocrlf=false", "core.eol=lf",
    "core.sparseCheckout=false", "core.sparseCheckoutCone=false",
    "submodule.recurse=false", "fetch.recurseSubmodules=false",
    "maintenance.auto=false", "gc.auto=0",
)
_GIT_ENV = {
    "PATH": "/usr/bin:/bin", "LC_ALL": "C",
    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
    "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1",
    "GIT_ALLOW_PROTOCOL": "", "GIT_ATTR_NOSYSTEM": "1",
}
_FIXTURE_ENV = {
    **_GIT_ENV,
    "GIT_AUTHOR_NAME": "hyeonsangjeon", "GIT_AUTHOR_EMAIL": "wingnut0310@gmail.com",
    "GIT_COMMITTER_NAME": "hyeonsangjeon", "GIT_COMMITTER_EMAIL": "wingnut0310@gmail.com",
    "GIT_AUTHOR_DATE": "2026-09-19T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-09-19T00:00:00+00:00",
}
_PREPARER_SOURCE = "batch-runner/gpt54_disposable_checkout.py"


def _git_prefix() -> list[str]:
    result = ["/usr/bin/git", "--no-replace-objects"]
    for setting in _GIT_SETTINGS:
        result.extend(("-c", setting))
    return [*result, "-C"]


def _allow_only_temporary_git(monkeypatch: Any, tmp_path: Path) -> tuple[list, list]:
    """Keep all external guards; admit only bounded Git in this case's tree.

    Both wrappers are necessary: the saved real ``run`` still calls the patched
    ``Popen``. No inherited environment or arbitrary executable is forwarded.
    """
    real_run, real_popen = subprocess.run, subprocess.Popen
    forbidden = _guards(monkeypatch)
    production_calls: list[tuple[Path, tuple[str, ...]]] = []
    prefix = _git_prefix()

    def checked(command: Any, kwargs: dict[str, Any]) -> tuple[Path, tuple[str, ...], bool]:
        if (type(command) not in (list, tuple) or not all(type(item) is str for item in command)
                or list(command[:len(prefix)]) != prefix or len(command) <= len(prefix) + 1
                or kwargs.get("shell") or kwargs.get("executable") is not None
                or kwargs.get("cwd") is not None
                or kwargs.get("stdin") != subprocess.DEVNULL
                or kwargs.get("stdout") != subprocess.PIPE
                or kwargs.get("stderr") != subprocess.PIPE):
            pytest.fail("only a fixed, closed-stdin local Git command is permitted")
        environment = kwargs.get("env")
        fixture = environment == _FIXTURE_ENV
        if not fixture and environment != _GIT_ENV:
            # Never include environment contents in assertion output.
            pytest.fail("Git attempted to inherit caller configuration or credentials")
        repository = Path(command[len(prefix)])
        if not repository.is_absolute() or not repository.resolve().is_relative_to(tmp_path.resolve()):
            pytest.fail("Git escaped the per-case temporary repository")
        args = tuple(command[len(prefix) + 1:])
        read_commands = {"rev-parse", "for-each-ref", "status", "cat-file", "ls-tree", "symbolic-ref"}
        if args[0] == "worktree":
            if len(args) == 6 and args[:4] == ("worktree", "add", "--detach", "--"):
                destination = Path(args[4])
                if (not destination.is_absolute()
                        or not destination.resolve().is_relative_to(tmp_path.resolve())
                        or not destination.is_dir() or any(destination.iterdir())):
                    pytest.fail("worktree add did not receive the exclusively created empty directory")
            else:
                pytest.fail("unexpected worktree mutation or cleanup")
        elif args[0] == "config":
            if not fixture and args[1:3] != ("--name-only", "--get-regexp"):
                pytest.fail("preparer attempted to modify Git configuration")
        elif args[0] not in read_commands and not (fixture and args[0] in {"init", "add", "commit", "tag"}):
            pytest.fail("unexpected local Git command")
        return repository, args, fixture

    def checked_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        repository, command_args, fixture = checked(command, kwargs)
        if args or kwargs.get("timeout") != 60 or kwargs.get("check") is not False:
            pytest.fail("local Git must use the fixed bounded invocation")
        if not fixture:
            production_calls.append((repository, command_args))
        return real_run(command, **kwargs)

    def checked_popen(command: Any, *args: Any, **kwargs: Any) -> Any:
        checked(command, kwargs)
        if args:
            pytest.fail("unexpected positional subprocess options")
        return real_popen(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", checked_run)
    monkeypatch.setattr(subprocess, "Popen", checked_popen)
    return forbidden, production_calls


def _fixture_git(repository: Path, *args: str, ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[bytes]:
    """Use only the guarded temporary repository; never change live identity."""
    result = subprocess.run(
        [*_git_prefix(), str(repository), *args], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(_FIXTURE_ENV),
        timeout=60, check=False,
    )
    if result.returncode not in ok:
        pytest.fail("temporary Git fixture command failed")
    return result


def _commit_fixture(repository: Path, message: str) -> str:
    _fixture_git(repository, "add", "--all")
    _fixture_git(repository, "commit", "--quiet", "-m", message)
    return _fixture_git(repository, "rev-parse", "--verify", "HEAD").stdout.decode().strip()


def _source_state(repository: Path) -> dict[str, Any]:
    """Exclude legitimate new worktree registrations, not the caller's state."""
    tree = _tree_snapshot(repository)
    return {
        "head": _fixture_git(repository, "rev-parse", "--verify", "HEAD").stdout,
        "refs": _fixture_git(repository, "for-each-ref", "--format=%(refname) %(objectname)").stdout,
        "metadata": {name: (repository / ".git" / name).read_bytes()
                     for name in ("HEAD", "index", "config")},
        "hooks": _tree_snapshot(repository / ".git/hooks"),
        "files": {name: value for name, value in tree.items()
                  if name != ".git" and not name.startswith(".git/")},
    }


def _sidecars(destination: Path) -> tuple[Path, Path]:
    return (
        destination.with_name(f".{destination.name}.comparison-checkout-reserved.json"),
        destination.with_name(f".{destination.name}.comparison-checkout-quarantine.json"),
    )


def _assert_ready(
    destination: Path, marker: dict[str, Any], *, repository: Path,
    reviewed_sha: str, reviewed_tree: str, plan: Any, index: int,
    manifest: dict[str, Any], inputs: dict[str, Any], oracle: dict[str, Any],
    records: dict[str, Any], reviewed_files: dict[str, bytes],
) -> None:
    run, grading_run = plan.dispatch.runs[index], plan.runs[index]
    config_bytes = (destination / config_bundle.READY_PATH).read_bytes()
    input_bytes = (destination / input_bundle.READY_PATH).read_bytes()
    config_marker, input_marker = json.loads(config_bytes), json.loads(input_bytes)
    linkage = {
        "attestation_version": "gpt54-prepared-input-attestation-v1",
        "binding_version": "gpt54-pre-execution-input-v1",
        "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
        "manifest_sha256": plan.dispatch.manifest_sha256,
        "combined_plan_sha256": _identity(plan.canonical_bytes())["sha256"],
        "source_pins_sha256": _identity(plan.dispatch.source_pins_json.encode())["sha256"],
        "config_sha256": _identity(run.config_json.encode())["sha256"],
        "capture_path": "batch-runner/workspace/pre-execution-input.json",
    }
    intent = {
        "reviewed_source_sha": reviewed_sha, "source_base_sha": plan.dispatch.source_base_sha,
        "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
        "abba_index": index, "task_ids": list(run.task_ids),
        "manifest_sha256": plan.dispatch.manifest_sha256,
        "combined_plan_sha256": _identity(plan.canonical_bytes())["sha256"],
        "source_pins": manifest["source_pins"],
    }
    expected = {
        "checkout_version": "gpt54-disposable-checkout-v1", **intent,
        "reviewed_tree_sha": reviewed_tree,
        "bundles": {
            "config": {"path": config_bundle.READY_PATH, **_identity(config_bytes)},
            "input": {"path": input_bundle.READY_PATH, **_identity(input_bytes)},
        },
        "attestation_linkage": linkage,
        "evidence_boundary": "local_reviewed_checkout_and_bundles",
    }
    assert marker == expected
    assert (destination / "comparison-checkout-ready.json").read_bytes() == _json(expected)
    reservation, quarantine = _sidecars(destination)
    assert reservation.read_bytes() == _json({
        "reservation_version": "gpt54-disposable-checkout-reservation-v1",
        "ready_path": "comparison-checkout-ready.json", "state": "reserved_not_ready", **intent,
    })
    assert not quarantine.exists()
    assert config_marker["attestation_linkage"] == linkage
    assert config_bytes == _json(config_marker) and input_bytes == _json(input_marker)
    assert input_marker["input_identity"] == {key: oracle[key] for key in (
        "binding_version", "manifest_sha256", "combined_plan_sha256", "source_pins_sha256",
        "dataset", "task_ids", "ordered_source_projection_sha256", "needs_files_policy",
    )}
    assert [row["task_id"] for row in input_marker["tasks"]] == list(run.task_ids)
    assert len(run.task_ids) == 5
    assert reviewed_sha != plan.dispatch.source_base_sha
    assert len(manifest["source_pins"]) == 34
    assert set(manifest["source_pins"]) == preflight.REQUIRED_SOURCES
    assert _PREPARER_SOURCE in manifest["source_pins"]
    assert not ({"launch_allowed", "full_220_allowed", "approval"} & marker.keys())
    assert plan.as_dict()["launch_allowed"] is plan.as_dict()["full_220_allowed"] is False
    assert str(repository).encode() not in _json(marker)
    assert str(destination).encode() not in _json(marker)
    exact_files = {
        **reviewed_files,
        "comparison-plan.json": plan.canonical_bytes(),
        run.config_path: run.config_json.encode(),
        grading_run.grader_config_path: grading_run.grader_config_json.encode(),
        grading_run.experiment_config_path: grading_run.experiment_config_json.encode(),
        input_bundle.PARQUET_PATH: inputs["dataset_parquet"].read_bytes(),
        **{input_bundle.DATASET_ROOT + "/" + name: (inputs["reference_root"] / name).read_bytes()
           for name in records},
    }
    for name, data in exact_files.items():
        path = destination / name
        assert path.read_bytes() == data
        assert not path.is_symlink() and path.stat().st_nlink == 1
    assert _fixture_git(destination, "rev-parse", "--verify", "HEAD").stdout == reviewed_sha.encode() + b"\n"
    symbolic = _fixture_git(destination, "symbolic-ref", "--quiet", "HEAD", ok=(1,))
    assert symbolic.stdout == b""
    assert (destination / ".git").is_file()
    assert not (destination / "caller-only.txt").exists()
    assert not (destination / "batch-runner/workspace").exists()


@pytest.mark.parametrize("case", [
    "v2_r1", "codex_r1", "codex_r2", "v2_r2",
    "moving_branch_dirty_pins", "ambient_environment_and_hooks",
    "sha_short", "sha_ref", "sha_unknown", "sha_uppercase", "sha_tag", "sha_tree", "sha_historical",
    "invalid_recipe", "invalid_combined_plan", "missing_source_pin", "changed_source_pin",
    "different_common_directory", "tracked_tree_drift", "pinned_source_drift", "wrong_or_attached_head",
    "existing_directory", "existing_file", "existing_reservation", "existing_quarantine",
    "destination_symlink", "dangling_destination", "parent_symlink", "parent_traversal",
    "source_overlap", "input_overlap",
    "committed_symlink", "committed_generated_target", "committed_pin_drift", "configured_filter",
    "failure_reservation", "failure_git_before", "failure_git_after", "failure_config_after",
    "failure_input_after", "failure_final_verification", "bundle_markers_drift",
])
def test_disposable_checkout_is_reviewed_local_and_quarantines_failures(
    case: str, tmp_path: Path, monkeypatch: Any, _input_bundle_seed: Any, capsys: Any,
) -> None:
    forbidden, git_calls = _allow_only_temporary_git(monkeypatch, tmp_path)
    _input_bundle_seed.install(monkeypatch)
    oracle_root = tmp_path / "independent-oracle"
    oracle_root.mkdir()
    inputs, captures, _, _, records = _input_bundle_seed.inputs(oracle_root, monkeypatch, "identical")
    plan = _input_bundle_seed.plan
    index = {"codex_r1": 1, "codex_r2": 2, "v2_r2": 3}.get(case, 0)
    run = plan.dispatch.runs[index]
    manifest, combined = deepcopy(inputs["manifest"]), plan.as_dict()
    repository, destination = tmp_path / "caller-repository", tmp_path / "reviewed-run"
    _bundle_fixture(repository, manifest=manifest, combined_plan=combined, run=run, materialize=False)
    note = repository / "tracked-note.txt"
    note.write_bytes(b"reviewed commit bytes\n")
    if case == "committed_symlink":
        (repository / "tracked-link").symlink_to(oracle_root, target_is_directory=True)
    elif case == "committed_generated_target":
        (repository / "comparison-plan.json").write_bytes(plan.canonical_bytes())
    elif case == "committed_pin_drift":
        pinned = repository / _PREPARER_SOURCE
        pinned.write_bytes(pinned.read_bytes() + b"\n# fixture commit differs from the supplied source pin\n")
    elif case == "configured_filter":
        (repository / ".gitattributes").write_bytes(b"tracked-note.txt filter=fixture\n")
    _fixture_git(repository, "init", "--quiet", "--initial-branch=fixture-main", "--object-format=sha1", "--template=")
    reviewed_sha = _commit_fixture(repository, "Reviewed temporary source")
    reviewed_tree = _fixture_git(repository, "rev-parse", reviewed_sha + "^{tree}").stdout.decode().strip()
    reviewed_files = {name: (repository / name).read_bytes()
                      for name in (*manifest["source_pins"], config_bundle.MANIFEST_PATH, "tracked-note.txt")}
    if case == "moving_branch_dirty_pins":
        note.write_bytes(b"later source branch commit\n")
        assert _commit_fixture(repository, "Move temporary caller branch") != reviewed_sha
        (repository / _PREPARER_SOURCE).write_bytes(b"caller edit must not enter the reviewed checkout\n")
    # Every case proves that dirty caller files are neither copied nor repaired.
    note.write_bytes(b"uncommitted caller change\n")
    (repository / "caller-only.txt").write_bytes(b"untracked caller bytes\n")
    monkeypatch.setattr(preparer, "TRUSTED_ROOT", repository)
    sentinel = tmp_path / "must-not-execute"
    if case == "configured_filter":
        _fixture_git(repository, "config", "--local", "filter.fixture.smudge",
                     "printf filter > " + shlex.quote(str(sentinel)))
    elif case == "ambient_environment_and_hooks":
        hook = repository / ".git/hooks/post-checkout"
        hook.parent.mkdir(exist_ok=True)
        hook.write_text("#!/bin/sh\nprintf hook > " + shlex.quote(str(sentinel)) + "\n")
        hook.chmod(0o755)
        fake_bin = tmp_path / "hostile-path"
        fake_bin.mkdir()
        fake_git = fake_bin / "git"
        fake_git.write_text("#!/bin/sh\nprintf path > " + shlex.quote(str(sentinel)) + "\nexit 91\n")
        fake_git.chmod(0o755)
        for name, value in {
            "PATH": str(fake_bin), "GIT_DIR": str(tmp_path / "wrong-git"),
            "GIT_WORK_TREE": str(oracle_root), "GIT_INDEX_FILE": str(tmp_path / "wrong-index"),
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath",
            "GIT_CONFIG_VALUE_0": str(hook.parent),
            "GIT_CONFIG_GLOBAL": str(tmp_path / "untrusted-global-config"),
            "OPENAI_API_KEY": "fixture-do-not-forward", "AZURE_API_KEY": "fixture-do-not-forward",
            "GH_TOKEN": "fixture-do-not-forward",
        }.items():
            monkeypatch.setenv(name, value)

    supplied_sha, supplied_run = reviewed_sha, run
    if case == "sha_tag":
        _fixture_git(repository, "tag", "--annotate", "fixture-tag", "--message", "Temporary tag", reviewed_sha)
        supplied_sha = _fixture_git(repository, "rev-parse", "refs/tags/fixture-tag").stdout.decode().strip()
    elif case.startswith("sha_"):
        supplied_sha = {
            "sha_short": reviewed_sha[:12], "sha_ref": "HEAD", "sha_unknown": "0" * 40,
            "sha_uppercase": reviewed_sha.upper(), "sha_tree": reviewed_tree,
            "sha_historical": plan.dispatch.source_base_sha,
        }[case]
    elif case == "invalid_recipe":
        supplied_run = replace(run, repeat=True)
    elif case == "invalid_combined_plan":
        combined["launch_allowed"] = True
    elif case == "missing_source_pin":
        del manifest["source_pins"][_PREPARER_SOURCE]
    elif case == "changed_source_pin":
        manifest["source_pins"][_PREPARER_SOURCE] = "0" * 64

    if case == "existing_directory":
        destination.mkdir()
    elif case == "existing_file":
        destination.write_bytes(b"do not overwrite\n")
    elif case in {"existing_reservation", "existing_quarantine"}:
        _sidecars(destination)[case == "existing_quarantine"].write_bytes(b"do not overwrite\n")
    elif case == "destination_symlink":
        destination.symlink_to(oracle_root, target_is_directory=True)
    elif case == "dangling_destination":
        destination.symlink_to(tmp_path / "absent-link-target", target_is_directory=True)
    elif case == "parent_symlink":
        parent = tmp_path / "linked-parent"
        parent.symlink_to(oracle_root, target_is_directory=True)
        destination = parent / destination.name
    elif case == "parent_traversal":
        destination = tmp_path / ".." / tmp_path.name / destination.name
    elif case == "source_overlap":
        destination = repository / "must-not-create"
    elif case == "input_overlap":
        destination = inputs["reference_root"] / "must-not-create"

    kwargs = {
        "repository": repository, "reviewed_source_sha": supplied_sha, "destination": destination,
        "manifest": manifest, "combined_plan": combined,
    }
    if case == "sha_ref":
        cli_plan = tmp_path / "cli-combined-plan.json"
        cli_plan.write_bytes(_json(combined))

    def prepare() -> dict[str, Any]:
        return preparer.prepare_disposable_checkout(
            supplied_run, **kwargs, dataset_parquet=inputs["dataset_parquet"],
            reference_root=inputs["reference_root"],
        )

    real_verify = preparer.verify_disposable_checkout

    def verify() -> dict[str, Any]:
        return real_verify(supplied_run, **kwargs)

    source_before, oracle_before = _source_state(repository), _tree_snapshot(oracle_root)
    reservation, quarantine = _sidecars(destination)
    ready = destination / preparer.READY_PATH
    rejected_before_reservation = (
        case.startswith("sha_") or case.startswith("invalid_") or case.startswith("existing_")
        or case in {
            "missing_source_pin", "changed_source_pin", "destination_symlink", "dangling_destination", "parent_symlink",
            "parent_traversal", "source_overlap", "input_overlap", "committed_symlink",
            "committed_generated_target", "committed_pin_drift", "configured_filter",
        }
    )
    if rejected_before_reservation:
        before = _tree_snapshot(tmp_path)
        with pytest.raises(preparer.DisposableCheckoutRefused) as refusal:
            prepare()
        if case == "committed_pin_drift":
            assert str(refusal.value.__cause__) == "reviewed source pin mismatch"
        if case == "sha_ref":
            capsys.readouterr()
            assert preparer.main([
                "--repository", str(repository), "--reviewed-source-sha", "HEAD",
                "--destination", str(destination),
                "--manifest", str(repository / config_bundle.MANIFEST_PATH),
                "--combined-plan", str(cli_plan), "--run-id", run.run_id,
                "--dataset-parquet", str(inputs["dataset_parquet"]),
                "--reference-root", str(inputs["reference_root"]),
            ]) == 2
            output = capsys.readouterr()
            assert json.loads(output.out) == {
                "prepared": False,
                "error": "a caller-reviewed full lowercase 40-hex commit SHA is required",
            }
            assert output.err == ""
        assert _tree_snapshot(tmp_path) == before
        assert not any(args[:2] == ("worktree", "add") for _, args in git_calls)
    elif case.startswith("failure_"):
        injected: list[str] = []
        if case == "failure_reservation":
            real_write = writer._write_no_clobber

            def interrupted_reservation(path: Path, data: bytes) -> None:
                if path == reservation:
                    injected.append("reservation")
                    raise OSError("fixture interrupts first reservation publication")
                real_write(path, data)

            monkeypatch.setattr(writer, "_write_no_clobber", interrupted_reservation)
        elif case.startswith("failure_git_"):
            real_git = preparer._git

            def interrupted_git(root: Path, *args: str, **options: Any) -> Any:
                if args[:2] == ("worktree", "add"):
                    assert destination.is_dir() and not any(destination.iterdir())
                    injected.append("detached_checkout")
                    if case == "failure_git_after":
                        real_git(root, *args, **options)
                    raise OSError("fixture interrupts local worktree creation")
                return real_git(root, *args, **options)

            monkeypatch.setattr(preparer, "_git", interrupted_git)
        else:
            name, phase = {
                "failure_config_after": ("materialize_run_config_bundle", "config_bundle"),
                "failure_input_after": ("materialize_run_input_bundle", "input_bundle"),
                "failure_final_verification": ("verify_disposable_checkout", "ready_verification"),
            }[case]
            original = getattr(preparer, name)

            def interrupted_helper(*args: Any, **options: Any) -> None:
                original(*args, **options)
                injected.append(phase)
                raise OSError("fixture interrupts completed helper")

            monkeypatch.setattr(preparer, name, interrupted_helper)
        with pytest.raises(preparer.DisposableCheckoutRefused) as failure:
            prepare()
        assert len(injected) == 1
        for path in (destination, reservation, quarantine):
            assert str(path) in str(failure.value)
        assert "manual disposal required" in str(failure.value)
        assert quarantine.is_file()
        quarantine_marker = json.loads(quarantine.read_bytes())
        assert quarantine_marker == {
            "quarantine_version": "gpt54-disposable-checkout-quarantine-v1",
            "reservation": reservation.name, "ready_path": preparer.READY_PATH,
            "phase": injected[0], "failure_type": "OSError",
            "disposition": "manual_disposal_required_no_reuse",
        }
        assert quarantine.read_bytes() == _json(quarantine_marker)
        assert reservation.exists() is (case != "failure_reservation")
        assert destination.exists() is (case != "failure_reservation")
        assert ready.exists() is (case == "failure_final_verification")
        before_retry = _tree_snapshot(tmp_path)
        with pytest.raises(preparer.DisposableCheckoutRefused):
            prepare()
        with pytest.raises(preparer.DisposableCheckoutRefused, match="quarantined"):
            verify()
        assert _tree_snapshot(tmp_path) == before_retry
        assert len(injected) == 1
    else:
        marker = prepare()
        _assert_ready(
            destination, marker, repository=repository, reviewed_sha=reviewed_sha,
            reviewed_tree=reviewed_tree, plan=plan, index=index, manifest=manifest,
            inputs=inputs, oracle=captures[index], records=records, reviewed_files=reviewed_files,
        )
        if case == "v2_r1":
            inspection = preflight.inspect_plan(manifest, grading_plan=combined)
            assert inspection["configuration_valid"] is True
            assert inspection["launch_allowed"] is inspection["full_220_allowed"] is False
            assert inspection["disposable_checkout"] == {
                "checkout_version": "gpt54-disposable-checkout-v1",
                "preparer": "gpt54_disposable_checkout.prepare_disposable_checkout",
                "ready_marker": "comparison-checkout-ready.json",
                "reviewed_source_sha": "required_external_full_commit_sha_not_source_base",
                "git_mutation": "worktree add --detach",
                "required_runs": [row.run_id for row in plan.dispatch.runs],
                "failure_policy": "retain_reservation_and_quarantine_no_reuse_or_cleanup",
                "evidence_boundary": "local_reviewed_checkout_and_bundles",
            }
            assert "comparison_materialization_and_workflow_gates_not_wired" in inspection["launch_blockers"]
        before_verify = _tree_snapshot(tmp_path)
        assert verify() == marker
        assert _tree_snapshot(tmp_path) == before_verify
        if case in {"tracked_tree_drift", "pinned_source_drift"}:
            (destination / (_PREPARER_SOURCE if case == "pinned_source_drift" else "tracked-note.txt")).write_bytes(
                b"altered after preparation\n",
            )
            before = _tree_snapshot(tmp_path)
            with pytest.raises(preparer.DisposableCheckoutRefused):
                verify()
            assert _tree_snapshot(tmp_path) == before
        elif case == "wrong_or_attached_head":
            gitdir = Path(_fixture_git(destination, "rev-parse", "--absolute-git-dir").stdout.decode().strip())
            assert gitdir.is_relative_to(tmp_path)
            head_file = gitdir / "HEAD"
            original_head = head_file.read_bytes()
            for bad_head in (b"f" * 40 + b"\n", b"ref: refs/heads/fixture-main\n"):
                head_file.write_bytes(bad_head)
                before = _tree_snapshot(tmp_path)
                with pytest.raises(preparer.DisposableCheckoutRefused):
                    verify()
                assert _tree_snapshot(tmp_path) == before
                head_file.write_bytes(original_head)
        elif case == "different_common_directory":
            other = tmp_path / "independent-repository"
            _bundle_fixture(other, manifest=manifest, combined_plan=combined, run=run, materialize=False)
            (other / "tracked-note.txt").write_bytes(b"reviewed commit bytes\n")
            _fixture_git(other, "init", "--quiet", "--initial-branch=fixture-main", "--object-format=sha1", "--template=")
            assert _commit_fixture(other, "Reviewed temporary source") == reviewed_sha
            kwargs["repository"] = other
            kwargs["destination"] = tmp_path / "different-common-must-not-create"
            before = _tree_snapshot(tmp_path)
            additions = [args for _, args in git_calls if args[:2] == ("worktree", "add")]
            with pytest.raises(preparer.DisposableCheckoutRefused, match="compiler's Git common directory"):
                prepare()
            assert [args for _, args in git_calls if args[:2] == ("worktree", "add")] == additions
            assert _tree_snapshot(tmp_path) == before
            kwargs["destination"] = destination
            monkeypatch.setattr(preparer, "TRUSTED_ROOT", other)
            before = _tree_snapshot(tmp_path)
            with pytest.raises(preparer.DisposableCheckoutRefused, match="different Git common directory"):
                verify()
            assert _tree_snapshot(tmp_path) == before
            kwargs["repository"] = repository
            monkeypatch.setattr(preparer, "TRUSTED_ROOT", repository)
        elif case == "bundle_markers_drift":
            for role in (config_bundle.READY_PATH, input_bundle.READY_PATH):
                path = destination / role
                held = path.with_name(path.name + ".fixture-held")
                path.rename(held)
                before = _tree_snapshot(tmp_path)
                with pytest.raises(preparer.DisposableCheckoutRefused):
                    verify()
                assert _tree_snapshot(tmp_path) == before
                held.rename(path)
            forged = {**marker, "reviewed_tree_sha": "0" * 40}
            ready.write_bytes(_json(forged))
            before = _tree_snapshot(tmp_path)
            with pytest.raises(preparer.DisposableCheckoutRefused):
                verify()
            assert _tree_snapshot(tmp_path) == before
            ready.write_bytes(_json(marker))
        before_retry = _tree_snapshot(tmp_path)
        with pytest.raises(preparer.DisposableCheckoutRefused):
            prepare()
        assert _tree_snapshot(tmp_path) == before_retry
        assert [args for _, args in git_calls if args[:2] == ("worktree", "add")] == [
            ("worktree", "add", "--detach", "--", str(destination), reviewed_sha),
        ]
    assert _source_state(repository) == source_before
    assert _tree_snapshot(oracle_root) == oracle_before
    assert not sentinel.exists()
    assert forbidden == []
