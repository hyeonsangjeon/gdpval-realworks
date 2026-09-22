"""One free selector: real local lineage before either runtime's provider seam."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

import gpt54_codex_input_capture as writer
import gpt54_comparison_preflight as preflight
import gpt54_disposable_checkout as preparer
import gpt54_run_config_bundle as config_bundle
import gpt54_run_input_bundle as input_bundle
import gpt54_v2_input_capture as v2_capture
import step1_prepare_tasks as step1
import step2_run_inference as step2
from core.prepared_fingerprint import prepared_fingerprint
from scripts import run_agentic_v2_stage as runner
from .test_gpt54_codex_input_capture import (
    ProviderBoundary, _runtime_fixture as _codex_fixture,
)
from .test_gpt54_disposable_checkout import (
    _allow_only_temporary_git, _commit_fixture, _fixture_git, _sidecars, _source_state,
)
from .test_gpt54_prepared_input_attestation import (
    _bundle_fixture, _json, _step0_manifest_source, _tree_snapshot,
)
from .test_gpt54_run_input_bundle import _input_bundle_seed
from .test_gpt54_v2_input_capture import _runtime_fixture as _v2_fixture


_RUNTIME_GIT = {
    ("rev-parse", "--show-toplevel"),
    ("rev-parse", "--path-format=absolute", "--git-common-dir"),
    ("rev-parse", "--absolute-git-dir"),
    ("rev-parse", "--verify", "--end-of-options", "HEAD^{commit}"),
    ("rev-parse", "--verify", "--end-of-options", "HEAD^{tree}"),
}
_REFUSALS = (
    "head_wrong", "head_attached", "head_moves", "ready_missing", "ready_altered",
    "reservation_missing", "reservation_altered", "config_missing", "config_altered",
    "input_missing", "input_altered", "quarantine", "wrong_run", "wrong_condition",
    "ready_symlink", "ready_hardlink", "path_traversal", "root_symlink",
    "stripped_opposite_ids", "config_marker_altered", "input_marker_altered",
    "ready_noncanonical",
)


def _runtime_paths(checkout: Path, monkeypatch: Any) -> None:
    for module in (step1, step2):
        monkeypatch.setattr(module, "WORKSPACE_DIR", checkout / "batch-runner/workspace")
        monkeypatch.setattr(module, "DEFAULT_LOCAL_PATH", checkout / writer.DATASET_ROOT)


def _entrypoint(condition: str, checkout: Path, run_id: str | None, monkeypatch: Any) -> Any:
    if condition == "codex":
        _runtime_paths(checkout, monkeypatch)
        return step2.run_inference(
            comparison_run_id=run_id, resume=False, max_retries=0, resume_max_rounds=0,
        )
    options = {
        "--stage": "advance_check_5", "--plan": str(checkout / writer.CONFIG_PATH),
        "--parquet": str(checkout / input_bundle.PARQUET_PATH),
        "--dataset-root": str(checkout / writer.DATASET_ROOT),
        "--into": str(checkout / "batch-runner/workspace"), "--run-id": run_id,
    }
    assert run_id is not None
    monkeypatch.setattr(sys, "argv", [
        "run_agentic_v2_stage.py", *(item for pair in options.items() for item in pair),
    ])
    return runner.main()


def _provider_boundaries(monkeypatch: Any, events: list[str]) -> None:
    """Stop before auth/client construction or even free V2 voice-safety work."""
    def auth_boundary(*args: Any, **kwargs: Any) -> None:
        events.append("auth_boundary")
        raise ProviderBoundary

    def free_boundary(*args: Any, **kwargs: Any) -> None:
        events.append("free_safety_boundary")
        raise ProviderBoundary

    monkeypatch.setenv("AZURE_AI_ROUTE_PROFILE", "offline-fixture")
    monkeypatch.setattr(step2, "_codex_connection_confirmed", lambda: True)
    monkeypatch.setattr(step2, "_require_host_may_carry_a_benchmark_run",
                        lambda mode: events.append("host_gate"))
    monkeypatch.setattr(step2.AzureAIRouteSettings, "from_env", auth_boundary)
    monkeypatch.setattr(runner, "run_stage_one_preflight", free_boundary)
    monkeypatch.setattr(runner, "load_task_catalog", preflight.load_task_catalog)
    monkeypatch.setattr(runner, "catalog_sha256", preflight.catalog_sha256)


def _unregistered_or_stripped(
    condition: str, case: str, tmp_path: Path, monkeypatch: Any, events: list[str],
) -> None:
    """Real legacy/capture readers, with lineage forbidden rather than faked."""
    if condition == "codex":
        checkout, run, payload, inputs, _ = _codex_fixture(tmp_path, monkeypatch, 1)
    else:
        checkout, run, inputs, _, _ = _v2_fixture(tmp_path, monkeypatch, 1)

    def no_lineage(*args: Any, **kwargs: Any) -> None:
        pytest.fail("absent/null controls must not enter the Git lineage boundary")

    # The old fixtures isolate capture checks using a labelled fake outer gate.
    # These cases instead prove the outer gate is never called at all.
    monkeypatch.setattr(preparer, "verify_runtime_checkout", no_lineage)
    _provider_boundaries(monkeypatch, events)
    config_path = checkout / writer.CONFIG_PATH
    if case == "stripped_opposite_ids":
        opposite_ids = [row.run_id for row in preflight.compile_dispatch_plan(inputs["manifest"]).runs
                        if row.condition != condition]
        assert len(opposite_ids) == 2
        for run_id in opposite_ids:
            for explicit_null in (False, True):
                if condition == "codex":
                    payload["experiment_id"] = run_id
                    payload["execution"].pop("comparison_input_capture", None)
                    if explicit_null:
                        payload["execution"]["comparison_input_capture"] = None
                    payload["prepared_fingerprint"] = prepared_fingerprint(payload)
                    (checkout / writer.PREPARED_PATH).write_bytes(_json(payload))
                else:
                    config = json.loads(run.config_json)
                    config.pop("comparison_input_capture")
                    if explicit_null:
                        config["comparison_input_capture"] = None
                    config_path.write_bytes(_json(config))
                before = _tree_snapshot(tmp_path)
                if condition == "codex":
                    with pytest.raises(writer.CodexInputCaptureRefused):
                        _entrypoint(condition, checkout, None, monkeypatch)
                else:
                    assert _entrypoint(condition, checkout, run_id, monkeypatch) == 1
                    assert not (checkout / writer.CAPTURE_PATH).exists()
                assert _tree_snapshot(tmp_path) == before
                assert events == []
        return

    assert case == "legacy_absent_and_null"
    config = (preflight.load_plan(preflight.ROOT / preflight.CODEX_TEMPLATE)
              if condition == "codex" else json.loads(run.config_json))
    control_owner = config["execution"] if condition == "codex" else config
    control_owner.pop("comparison_input_capture", None)
    serialized = []
    for explicit_null in (False, True):
        if explicit_null:
            control_owner["comparison_input_capture"] = None
        config_path.write_bytes(_json(config))
        if condition == "codex":
            prepared = step1.prepare_tasks(str(config_path))
            assert "comparison_input_capture" not in prepared["execution"]
            serialized.append((checkout / writer.PREPARED_PATH).read_bytes())
        before = _tree_snapshot(tmp_path)
        with pytest.raises(ProviderBoundary):
            _entrypoint(condition, checkout, None if condition == "codex" else "legacy-run", monkeypatch)
        assert _tree_snapshot(tmp_path) == before
    if condition == "codex":
        assert serialized[0] == serialized[1]
        assert events == ["host_gate", "auth_boundary"] * 2
    else:
        assert events == ["free_safety_boundary"] * 2
        assert not (checkout / writer.CAPTURE_PATH).exists()


@pytest.mark.parametrize(("condition", "case"), [
    ("sandbox_v2", "r1"), ("codex", "r1"), ("codex", "r2"), ("sandbox_v2", "r2"),
    *((condition, case) for condition in ("codex", "sandbox_v2")
      for case in ("legacy_absent_and_null", *_REFUSALS)),
])
def test_runtime_checkout_lineage_precedes_both_providers(
    condition: str, case: str, tmp_path: Path, monkeypatch: Any, _input_bundle_seed: Any,
) -> None:
    forbidden_calls, git_calls = _allow_only_temporary_git(monkeypatch, tmp_path)
    _input_bundle_seed.install(monkeypatch)
    events: list[str] = []
    if case in {"legacy_absent_and_null", "stripped_opposite_ids"}:
        _unregistered_or_stripped(condition, case, tmp_path, monkeypatch, events)
        assert forbidden_calls == git_calls == []
        return

    oracle_root = tmp_path / "independent-oracle"
    oracle_root.mkdir()
    inputs, captures, _, _, _ = _input_bundle_seed.inputs(oracle_root, monkeypatch, "identical")
    plan = _input_bundle_seed.plan
    index = (2 if case == "r2" else 1) if condition == "codex" else (3 if case == "r2" else 0)
    run = plan.dispatch.runs[index]
    repository, checkout = tmp_path / "caller-repository", tmp_path / "reviewed-run"
    _bundle_fixture(repository, manifest=inputs["manifest"], combined_plan=inputs["combined_plan"],
                    run=run, materialize=False)
    note = repository / "tracked-note.txt"
    note.write_bytes(b"reviewed source bytes\n")
    _fixture_git(repository, "init", "--quiet", "--initial-branch=fixture-main",
                 "--object-format=sha1", "--template=")
    reviewed_sha = _commit_fixture(repository, "Reviewed temporary source")
    note.write_bytes(b"uncommitted caller change\n")
    (repository / "caller-only.txt").write_bytes(b"untracked caller bytes\n")
    source_before, oracle_before = _source_state(repository), _tree_snapshot(oracle_root)
    monkeypatch.setattr(preparer, "TRUSTED_ROOT", repository)
    marker = preparer.prepare_disposable_checkout(
        run, repository=repository, reviewed_source_sha=reviewed_sha, destination=checkout,
        manifest=inputs["manifest"], combined_plan=inputs["combined_plan"],
        dataset_parquet=inputs["dataset_parquet"], reference_root=inputs["reference_root"],
        step0_manifest=_step0_manifest_source(inputs, run),
    )
    workspace = checkout / "batch-runner/workspace"
    workspace.mkdir(exist_ok=True)
    _runtime_paths(checkout, monkeypatch)
    if condition == "codex":
        payload = step1.prepare_tasks(str(checkout / writer.CONFIG_PATH))
        assert (checkout / writer.CAPTURE_PATH).read_bytes() == _json(captures[index])
    _provider_boundaries(monkeypatch, events)

    gitdir = Path(os.fsdecode(_fixture_git(checkout, "rev-parse", "--absolute-git-dir").stdout.rstrip(b"\n")))
    head = gitdir / "HEAD"
    assert head.read_bytes() == reviewed_sha.encode() + b"\n"
    reservation, quarantine = _sidecars(checkout)
    ready = checkout / preparer.READY_PATH
    runtime_root, requested_run = checkout, run.run_id
    changed_head = b"f" * 40 + b"\n"
    assert changed_head != head.read_bytes()
    moves = []
    if case == "head_wrong":
        head.write_bytes(changed_head)
    elif case == "head_attached":
        head.write_bytes(b"ref: refs/heads/fixture-main\n")
        assert _fixture_git(checkout, "rev-parse", "--verify", "HEAD").stdout == reviewed_sha.encode() + b"\n"
    elif case == "head_moves":
        real_marker = preparer._marker

        def move_after_bundles(*args: Any, **kwargs: Any) -> dict:
            result = real_marker(*args, **kwargs)
            assert moves == []
            head.write_bytes(changed_head)
            moves.append("head_changed_after_real_bundle_validation")
            return result

        monkeypatch.setattr(preparer, "_marker", move_after_bundles)
    elif case.endswith("_missing"):
        target = {
            "ready_missing": ready, "reservation_missing": reservation,
            "config_missing": checkout / config_bundle.READY_PATH,
            "input_missing": checkout / input_bundle.READY_PATH,
        }[case]
        target.rename(tmp_path / "held-missing-marker")
    elif case in {"ready_altered", "reservation_altered", "config_marker_altered", "input_marker_altered"}:
        target = {
            "ready_altered": ready, "reservation_altered": reservation,
            "config_marker_altered": checkout / config_bundle.READY_PATH,
            "input_marker_altered": checkout / input_bundle.READY_PATH,
        }[case]
        document = json.loads(target.read_bytes())
        document["unexpected_authorization"] = True
        target.write_bytes(_json(document))
    elif case == "ready_noncanonical":
        ready.write_bytes(ready.read_bytes() + b"\n")
    elif case in {"config_altered", "input_altered"}:
        target = checkout / (writer.CONFIG_PATH if case == "config_altered" else input_bundle.PARQUET_PATH)
        target.write_bytes(target.read_bytes() + b"\n")
    elif case == "quarantine":
        quarantine.write_bytes(_json({"state": "quarantined"}))
    elif case == "wrong_run":
        requested_run = next(row.run_id for row in plan.dispatch.runs
                             if row.condition == condition and row.run_id != run.run_id)
        if condition == "codex":
            payload["execution"]["comparison_input_capture"]["run_id"] = requested_run
            payload["experiment_id"] = requested_run
            payload["prepared_fingerprint"] = prepared_fingerprint(payload)
            (checkout / writer.PREPARED_PATH).write_bytes(_json(payload))
    elif case == "wrong_condition":
        for target in (ready, reservation):
            document = json.loads(target.read_bytes())
            document["condition"] = "sandbox_v2" if condition == "codex" else "codex"
            target.write_bytes(_json(document))
    elif case in {"ready_symlink", "ready_hardlink"}:
        held = tmp_path / "held-ready-marker"
        ready.rename(held)
        if case == "ready_symlink":
            ready.symlink_to(held)
        else:
            os.link(held, ready)
    elif case == "path_traversal":
        runtime_root = checkout / ".." / checkout.name
    elif case == "root_symlink":
        runtime_root = tmp_path / "aliased-checkout"
        runtime_root.symlink_to(checkout, target_is_directory=True)

    # Preparation uses the caller's reviewed source. Runtime must not need it,
    # inspect its config/status, or call the external-source verifier again.
    def no_external_source(*args: Any, **kwargs: Any) -> None:
        pytest.fail("runtime attempted to reuse preparation's external-source verifier")

    monkeypatch.setattr(preparer, "verify_disposable_checkout", no_external_source)
    monkeypatch.setattr(preparer, "_common", no_external_source)
    monkeypatch.setattr(preparer, "_reviewed_commit", no_external_source)
    monkeypatch.setattr(preparer, "TRUSTED_ROOT", tmp_path / "unavailable-external-source")
    real_git, real_lineage = preparer._git, preparer.verify_runtime_checkout
    git_calls.clear()

    def read_only_git(repository: Path, *args: str, **kwargs: Any) -> Any:
        assert repository == checkout and args in _RUNTIME_GIT
        return real_git(repository, *args, **kwargs)

    def observed_lineage(**kwargs: Any) -> dict:
        events.append("lineage")
        assert kwargs == {"checkout": checkout, "run_id": requested_run, "condition": condition}
        result = real_lineage(**kwargs)
        assert result == marker
        assert not ({"launch_allowed", "full_220_allowed", "approval"} & result.keys())
        events.append("lineage_ok")
        return result

    real_binding = writer._binding if condition == "codex" else v2_capture._binding

    def observed_binding(*args: Any, **kwargs: Any) -> Any:
        events.append("binding")
        return real_binding(*args, **kwargs)

    monkeypatch.setattr(preparer, "_git", read_only_git)
    monkeypatch.setattr(preparer, "verify_runtime_checkout", observed_lineage)
    monkeypatch.setattr(writer if condition == "codex" else v2_capture, "_binding", observed_binding)
    before = _tree_snapshot(tmp_path)
    if case in {"path_traversal", "root_symlink"}:
        # Runtime role checks may reject these before lineage. The public gate
        # must also refuse the same unsafe checkout spelling on its own.
        with pytest.raises(preparer.DisposableCheckoutRefused):
            real_lineage(checkout=runtime_root, run_id=requested_run, condition=condition)
        assert git_calls == []
    elif case == "wrong_condition":
        with pytest.raises(preparer.DisposableCheckoutRefused):
            real_lineage(checkout=checkout, run_id=requested_run,
                         condition="sandbox_v2" if condition == "codex" else "codex")

    if case in {"r1", "r2"}:
        with pytest.raises(ProviderBoundary):
            _entrypoint(condition, runtime_root, requested_run, monkeypatch)
        expected = (["lineage", "lineage_ok", "binding", "host_gate", "auth_boundary"]
                    if condition == "codex" else
                    ["lineage", "lineage_ok", "binding", "binding", "free_safety_boundary"])
        assert events == expected
        capture_path = checkout / writer.CAPTURE_PATH
        assert capture_path.read_bytes() == _json(captures[index])
        assert capture_path.stat().st_nlink == 1 and not capture_path.is_symlink()
        assert len(git_calls) == 10
        inspection = preflight.inspect_plan(inputs["manifest"], grading_plan=inputs["combined_plan"])
        assert inspection["configuration_valid"] is True
        assert inspection["runtime_checkout_lineage"] == {
            "verifier": "gpt54_disposable_checkout.verify_runtime_checkout",
            "required_runs": [row.run_id for row in plan.dispatch.runs],
            "entrypoints": ["step2_run_inference", "scripts/run_agentic_v2_stage"],
            "before": "provider_auth_client_free_safety_model_voice",
            "git_commands": ["rev-parse"], "external_source_worktree_required": False,
            "evidence_boundary": "local_reviewed_checkout_and_bundles",
        }
        assert len(inputs["manifest"]["source_pins"]) == 36
        assert set(inputs["manifest"]["source_pins"]) == preflight.REQUIRED_SOURCES
        assert inspection["launch_allowed"] is inspection["full_220_allowed"] is False
    else:
        if condition == "codex":
            with pytest.raises(writer.CodexInputCaptureRefused):
                _entrypoint(condition, runtime_root, requested_run, monkeypatch)
        else:
            assert _entrypoint(condition, runtime_root, requested_run, monkeypatch) == 1
            assert not (checkout / writer.CAPTURE_PATH).exists()
        assert events == ([] if case in {"path_traversal", "root_symlink"} else ["lineage"])

    after = _tree_snapshot(tmp_path)
    if case in {"r1", "r2"} and condition == "sandbox_v2":
        # Only the real capture writer may add a file after the read-only gate.
        new_capture = (checkout / writer.CAPTURE_PATH).relative_to(tmp_path).as_posix()
        assert new_capture not in before
        after.pop(new_capture)
    elif case == "head_moves":
        assert moves == ["head_changed_after_real_bundle_validation"]
        head_role = head.relative_to(tmp_path).as_posix()
        assert after[head_role][:2] == before[head_role][:2]
        assert after[head_role][2] == changed_head
        before[head_role] = after[head_role]  # Only the deliberate race injection.
    assert after == before
    assert _source_state(repository) == source_before
    assert _tree_snapshot(oracle_root) == oracle_before
    assert all(root == checkout and args in _RUNTIME_GIT for root, args in git_calls)
    assert forbidden_calls == []
