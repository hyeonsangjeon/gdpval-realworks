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
    _PROSPECTIVE_MANIFEST, _allow_only_temporary_git, _commit_fixture, _fixture_git,
    _sidecars, _source_state,
)
from .test_gpt54_prepared_input_attestation import (
    _bundle_fixture, _identity, _json, _step0_manifest_source, _tree_snapshot,
)
from .test_gpt54_run_input_bundle import _copy_files, _input_bundle_seed, _make_input_bundle_seed
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
    condition: str, case: str, tmp_path: Path, monkeypatch: Any,
    _input_bundle_seed: Any, capsys: pytest.CaptureFixture[str],
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
        result = real_binding(*args, **kwargs)
        events.append("binding_ok")
        return result

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
        capture_path = checkout / writer.CAPTURE_PATH
        if condition == "codex":
            with pytest.raises(
                writer.ComparisonRuntimeLaunchRefused,
                match="^comparison_runtime_launch_refused$",
            ) as refusal:
                _entrypoint(condition, runtime_root, requested_run, monkeypatch)
            assert type(refusal.value) is writer.ComparisonRuntimeLaunchRefused
            assert capture_path.read_bytes() == _json(captures[index])
            assert capture_path.stat().st_nlink == 1 and not capture_path.is_symlink()
        else:
            assert _entrypoint(condition, runtime_root, requested_run, monkeypatch) == 1
            assert "comparison_runtime_launch_refused" in capsys.readouterr().out.splitlines()
            assert not capture_path.exists()
        assert events == ["lineage", "lineage_ok", "binding", "binding_ok"]
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
        assert len(inputs["manifest"]["source_pins"]) == 37
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
    if case == "head_moves":
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


@pytest.fixture(scope="module")
def _anchored_input_seed(tmp_path_factory, frozen_local_comparison_source):
    # The sealed local-source profile is historical now. Current R must refuse
    # it; F supplies real positive source/closure bytes, not replacement pins.
    current = preflight.inspect_plan(preflight.load_plan(preflight.ROOT / _PROSPECTIVE_MANIFEST))
    assert current["configuration_valid"] is current["launch_allowed"] is False
    assert current["configuration_problems"] == [
        "source_pin:batch-runner/core/agentic_v2_conversation_runner.py",
        "source_pin:batch-runner/core/codex_runner.py",
    ]
    yield from _make_input_bundle_seed(
        tmp_path_factory, frozen_local_comparison_source, _PROSPECTIVE_MANIFEST,
    )


def _anchored_checkout(tmp_path, monkeypatch, seed, *, condition="sandbox_v2",
                       historical=False, substitute=False):
    forbidden, git_calls = _allow_only_temporary_git(monkeypatch, tmp_path)
    seed.install(monkeypatch)
    oracle = tmp_path / "synthetic-originals"
    oracle.mkdir()
    inputs, captures, _, _, _ = seed.inputs(oracle, monkeypatch, "identical")
    index = 1 if condition == "codex" else 0
    run = seed.plan.dispatch.runs[index]
    repository, checkout = tmp_path / "source", tmp_path / "prepared"
    _bundle_fixture(repository, manifest=inputs["manifest"], combined_plan=inputs["combined_plan"],
                    run=run, materialize=False)
    manifest_path = config_bundle.MANIFEST_PATH if historical else _PROSPECTIVE_MANIFEST
    if not historical:
        assert inputs["manifest"]["source_pins"] == preflight.load_plan()["source_pins"]
        (repository / manifest_path).write_bytes(b"# synthetic frozen-source profile\n" + _json(inputs["manifest"]))
        (repository / config_bundle.MANIFEST_PATH).write_bytes(
            (preflight.ROOT / config_bundle.MANIFEST_PATH).read_bytes(),
        )
    _fixture_git(repository, "init", "--quiet", "--initial-branch=fixture-main",
                 "--object-format=sha1", "--template=")
    anchor = reviewed_sha = _commit_fixture(repository, "Independently reviewed synthetic source")
    if substitute:
        path = repository / manifest_path
        path.write_bytes(path.read_bytes() + b"\n# Different committed manifest bytes\n")
        reviewed_sha = _commit_fixture(repository, "Different synthetic source, not the expected review")
        assert anchor != reviewed_sha
    monkeypatch.setattr(preparer, "TRUSTED_ROOT", repository)
    marker = preparer.prepare_disposable_checkout(
        run, repository=repository, reviewed_source_sha=reviewed_sha, destination=checkout,
        manifest=inputs["manifest"], combined_plan=inputs["combined_plan"], manifest_path=manifest_path,
        dataset_parquet=inputs["dataset_parquet"], reference_root=inputs["reference_root"],
        step0_manifest=_step0_manifest_source(inputs, run),
    )
    gitdir = Path(os.fsdecode(_fixture_git(checkout, "rev-parse", "--absolute-git-dir").stdout.rstrip(b"\n")))
    # Verification must not return to preparation or its external source root.
    def no_preparation(*args, **kwargs):
        pytest.fail("metadata verification entered an external preparation boundary")

    monkeypatch.setattr(preparer, "_reviewed_commit", no_preparation)
    monkeypatch.setattr(preparer, "_checkout_state", no_preparation)
    monkeypatch.setattr(preparer, "TRUSTED_ROOT", tmp_path / "unavailable-old-source")
    git_calls.clear()
    return {
        "repository": repository, "checkout": checkout, "anchor": anchor, "marker": marker,
        "run": run, "plan": seed.plan, "inputs": inputs, "captures": captures, "index": index,
        "head": gitdir / "HEAD", "manifest_path": manifest_path,
        "forbidden": forbidden, "git_calls": git_calls,
    }


def _rebind_synthetic_locator(checkout, manifest_identity):
    """An adversary's coherent mutable markers still cannot replace a Git blob."""
    config_path = checkout / config_bundle.READY_PATH
    config = json.loads(config_path.read_bytes())
    config["manifest_file"] = manifest_identity
    config_data = _json(config)
    config_path.write_bytes(config_data)
    input_path = checkout / input_bundle.READY_PATH
    inputs = json.loads(input_path.read_bytes())
    inputs["config_bundle"] = {"path": config_bundle.READY_PATH, **_identity(config_data)}
    input_data = _json(inputs)
    input_path.write_bytes(input_data)
    (checkout / input_bundle.RESERVATION_PATH).write_bytes(input_bundle._reservation(input_data))
    ready_path = checkout / preparer.READY_PATH
    ready = json.loads(ready_path.read_bytes())
    ready["bundles"] = {
        "config": {"path": config_bundle.READY_PATH, **_identity(config_data)},
        "input": {"path": input_bundle.READY_PATH, **_identity(input_data)},
    }
    ready_path.write_bytes(_json(ready))


@pytest.mark.parametrize("case", [
    "valid", "codex_valid", "omitted", "none", "empty", "short", "uppercase", "boolean", "ref", "tag_name",
    "tag_object", "tree_object", "blob_object", "wrong_anchor", "coherent_source_substitution",
    "ready_anchor", "wrong_tree", "head_wrong", "head_attached", "config_path", "config_digest",
    "config_oversize", "manifest_digest", "manifest_size", "manifest_oversize", "manifest_path",
    "untracked", "external", "url", "traversal", "wrong_directory", "backslash", "wrong_suffix",
    "symlink", "hardlink", "symlink_parent", "tracked_symlink", "tracked_tree", "blob_size", "blob_bytes",
    "quarantine", "reservation_missing", "reservation_altered", "ready_noncanonical",
    "input_bytes", "input_marker", "pinned_source",
    "head_race", "ready_race", "reservation_race", "quarantine_race", "manifest_race", "parent_race",
])
def test_anchored_prospective_verification(case, tmp_path, monkeypatch, _anchored_input_seed):
    f = _anchored_checkout(
        tmp_path, monkeypatch, _anchored_input_seed,
        condition="codex" if case == "codex_valid" else "sandbox_v2",
        substitute=case == "coherent_source_substitution",
    )
    root, run = f["checkout"], f["run"]
    ready = root / preparer.READY_PATH
    reservation, quarantine = _sidecars(root)
    source = root / f["manifest_path"]
    manifest_identity = {"path": f["manifest_path"], **_identity(source.read_bytes())}
    kwargs = {"checkout": root, "run_id": run.run_id, "condition": run.condition,
              "expected_reviewed_source_sha": f["anchor"]}
    # These inert ambient hints must not select the API's anchored mode.
    monkeypatch.setenv("EXPECTED_REVIEWED_SOURCE_SHA", f["anchor"])
    monkeypatch.setenv("COMPARISON_MANIFEST_PATH", f["manifest_path"])
    if case == "omitted":
        kwargs.pop("expected_reviewed_source_sha")
    elif case in {"none", "empty", "short", "uppercase", "boolean", "ref", "tag_name", "wrong_anchor"}:
        kwargs["expected_reviewed_source_sha"] = {
            "none": None, "empty": "", "short": f["anchor"][:12], "uppercase": f["anchor"].upper(),
            "boolean": True, "ref": "refs/heads/fixture-main", "tag_name": "fixture-tag", "wrong_anchor": "0" * 40,
        }[case]
    elif case in {"tag_object", "tree_object", "blob_object"}:
        repository = f["repository"]
        if case == "tag_object":
            _fixture_git(repository, "tag", "-a", "fixture-tag", "-m", "Synthetic tag", f["anchor"])
            revision = "fixture-tag"
        else:
            revision = f["anchor"] + ("^{tree}" if case == "tree_object" else ":" + f["manifest_path"])
        oid = _fixture_git(repository, "rev-parse", "--verify", revision).stdout.decode().strip()
        held = json.loads(ready.read_bytes())
        held["reviewed_source_sha"] = kwargs["expected_reviewed_source_sha"] = oid
        ready.write_bytes(_json(held))
        f["head"].write_bytes(oid.encode() + b"\n")
    elif case in {"ready_anchor", "wrong_tree", "config_path", "config_oversize"}:
        held = json.loads(ready.read_bytes())
        if case == "ready_anchor":
            held["reviewed_source_sha"] = "0" * 40
        elif case == "wrong_tree":
            held["reviewed_tree_sha"] = "0" * 40
        elif case == "config_path":
            held["bundles"]["config"]["path"] = "../substituted-config.json"
        else:
            held["bundles"]["config"]["size"] = 1024 * 1024 + 1
        ready.write_bytes(_json(held))
    elif case in {"head_wrong", "head_attached"}:
        f["head"].write_bytes(b"0" * 40 + b"\n" if case == "head_wrong" else b"ref: refs/heads/fixture-main\n")
    elif case == "config_digest":
        path = root / config_bundle.READY_PATH
        path.write_bytes(path.read_bytes().replace(b"local_config", b"false_config", 1))
    elif case in {"manifest_digest", "manifest_size", "manifest_oversize", "manifest_path"}:
        if case == "manifest_digest":
            manifest_identity["sha256"] = "0" * 64
        elif case == "manifest_size":
            manifest_identity["size"] += 1
        elif case == "manifest_oversize":
            manifest_identity["size"] = 1024 * 1024 + 1
        else:
            manifest_identity["path"] = config_bundle.MANIFEST_PATH
        _rebind_synthetic_locator(root, manifest_identity)
    elif case in {"untracked", "external", "url", "traversal", "wrong_directory", "backslash", "wrong_suffix"}:
        paths = {
            "untracked": preflight.ENVELOPE + "unreviewed.yaml",
            "external": str(tmp_path / "external.yaml"), "url": "https://example.invalid/profile.yaml",
            "traversal": preflight.ENVELOPE + "../execution_envelope/" + source.name,
            "wrong_directory": "batch-runner/profile.yaml", "backslash": f["manifest_path"].replace("/", "\\"),
            "wrong_suffix": preflight.ENVELOPE + "profile.json",
        }
        manifest_identity["path"] = paths[case]
        if case == "untracked":
            (root / paths[case]).write_bytes(source.read_bytes())
        _rebind_synthetic_locator(root, manifest_identity)
    elif case in {"symlink", "hardlink", "symlink_parent"}:
        held = tmp_path / "held-source"
        if case == "symlink_parent":
            source.parent.rename(held)
            source.parent.symlink_to(held, target_is_directory=True)
        else:
            source.rename(held)
            if case == "symlink":
                source.symlink_to(held)
            else:
                source.hardlink_to(held)
    elif case in {"tracked_symlink", "tracked_tree"}:
        repository_source = f["repository"] / f["manifest_path"]
        saved = repository_source.with_name("held-profile.yaml")
        repository_source.rename(saved)
        if case == "tracked_symlink":
            repository_source.symlink_to(saved.name)
        else:
            repository_source.mkdir()
            (repository_source / "member").write_bytes(b"not a regular manifest blob\n")
        anchor = _commit_fixture(f["repository"], "Synthetic nonregular tracked manifest")
        tree = _fixture_git(f["repository"], "rev-parse", anchor + "^{tree}").stdout.decode().strip()
        kwargs["expected_reviewed_source_sha"] = anchor
        held = json.loads(ready.read_bytes())
        held.update(reviewed_source_sha=anchor, reviewed_tree_sha=tree)
        ready.write_bytes(_json(held))
        f["head"].write_bytes(anchor.encode() + b"\n")
        reservation.write_bytes(preparer._reservation(f["plan"], f["index"], anchor))
    elif case in {"blob_size", "blob_bytes"}:
        data = source.read_bytes()
        source.write_bytes(data + b"\n# unreviewed\n" if case == "blob_size" else data.replace(b"synthetic", b"Synthetic", 1))
        _rebind_synthetic_locator(root, {"path": f["manifest_path"], **_identity(source.read_bytes())})
    elif case == "quarantine":
        quarantine.write_bytes(b"quarantined fixture\n")
        ready.unlink()  # Quarantine must take precedence even over missing markers/anchor errors.
        kwargs["expected_reviewed_source_sha"] = "malformed"
    elif case == "reservation_missing":
        reservation.rename(tmp_path / "held-reservation")
    elif case == "reservation_altered":
        reservation.write_bytes(reservation.read_bytes() + b"\n")
    elif case == "ready_noncanonical":
        ready.write_bytes(ready.read_bytes() + b"\n")
    elif case in {"input_bytes", "input_marker", "pinned_source"}:
        path = root / {
            "input_bytes": input_bundle.PARQUET_PATH, "input_marker": input_bundle.READY_PATH,
            "pinned_source": "batch-runner/gpt54_disposable_checkout.py",
        }[case]
        path.write_bytes(path.read_bytes() + b"\n")

    injected = []
    real_marker = preparer._marker
    if case.endswith("_race"):
        def after_real_bundles(*args, **options):
            result = real_marker(*args, **options)
            assert options == {} and args[-1] == f["manifest_path"]
            if case == "head_race":
                f["head"].write_bytes(b"0" * 40 + b"\n")
            elif case == "ready_race":
                ready.write_bytes(ready.read_bytes() + b"\n")
            elif case == "reservation_race":
                reservation.write_bytes(reservation.read_bytes() + b"\n")
            elif case == "quarantine_race":
                quarantine.write_bytes(b"quarantined after real bundle verification\n")
            elif case == "manifest_race":
                source.write_bytes(source.read_bytes() + b"\n# changed after real bundle verification\n")
            else:
                parent = source.parent
                files = tuple((path.relative_to(parent).as_posix(), path.read_bytes())
                              for path in sorted(parent.rglob("*")) if path.is_file())
                parent.rename(tmp_path / "held-envelope")
                _copy_files(parent, files)
            injected.append(_tree_snapshot(tmp_path))
            return result

        monkeypatch.setattr(preparer, "_marker", after_real_bundles)

    def no_capture(*args, **options):
        pytest.fail("read-only verification attempted capture publication")

    monkeypatch.setattr(writer, "_write_no_clobber", no_capture)
    f["git_calls"].clear()
    before = _tree_snapshot(tmp_path)
    if case in {"valid", "codex_valid"}:
        result = preparer.verify_runtime_checkout(**kwargs)
        assert result == f["marker"] and _json(result) == ready.read_bytes()
        assert result["evidence_boundary"] == "local_reviewed_checkout_and_bundles"
        assert not {"launch_allowed", "approval", "dispatch_allowed"}.intersection(result)
        assert len(f["inputs"]["manifest"]["source_pins"]) == 37
        assert set(f["inputs"]["manifest"]["source_pins"]) == preflight.REQUIRED_SOURCES
        assert f["plan"].as_dict()["launch_allowed"] is f["plan"].as_dict()["full_220_allowed"] is False
        assert (root, ("ls-tree", "-z", "--full-tree", f["anchor"], "--", f["manifest_path"])) in f["git_calls"]
        assert any(args[:2] == ("cat-file", "blob") for _, args in f["git_calls"])
    else:
        with pytest.raises(preparer.DisposableCheckoutRefused) as refusal:
            preparer.verify_runtime_checkout(**kwargs)
        if case in {"coherent_source_substitution", "wrong_anchor", "ready_anchor"}:
            assert str(refusal.value) == "runtime checkout differs from the expected reviewed commit"
            if case == "coherent_source_substitution":
                assert f["marker"]["reviewed_source_sha"] != f["anchor"]
        elif case in {"tag_object", "tree_object", "blob_object"}:
            assert str(refusal.value) == "expected reviewed source must name a commit object"
        elif case in {"empty", "short", "uppercase", "boolean", "ref", "tag_name"}:
            assert str(refusal.value) == "an independent reviewed full lowercase 40-hex commit SHA is required"
        elif case == "wrong_tree":
            assert str(refusal.value) == "runtime checkout tree differs from the expected reviewed commit"
        elif case == "untracked":
            assert str(refusal.value) == "anchored manifest requires one exact tracked blob"
        elif case in {"tracked_symlink", "tracked_tree"}:
            assert str(refusal.value) == "anchored manifest requires a regular tracked blob"
        elif case == "blob_size":
            assert str(refusal.value) == "anchored manifest tracked blob size mismatch"
        elif case == "blob_bytes":
            assert str(refusal.value) == "anchored manifest differs from the reviewed commit blob"
        elif case == "quarantine":
            assert str(refusal.value) == "quarantined runtime checkout cannot be used"
        elif case in {"omitted", "none"}:
            assert not any(args[0] in {"ls-tree", "cat-file"} for _, args in f["git_calls"])
    assert _tree_snapshot(tmp_path) == (injected[0] if injected else before)
    assert len(injected) == int(case.endswith("_race"))
    assert all(path == root and args[0] in {"rev-parse", "ls-tree", "cat-file"}
               for path, args in f["git_calls"])
    assert f["forbidden"] == []


@pytest.mark.parametrize("condition", ["codex", "sandbox_v2"])
def test_anchored_prospective_verification_keeps_default_runtime_refusal(
    condition, tmp_path, monkeypatch, _input_bundle_seed, capsys,
):
    """An anchored metadata result cannot enable either existing direct runtime."""
    f = _anchored_checkout(tmp_path, monkeypatch, _input_bundle_seed, condition=condition, historical=True)
    root, run = f["checkout"], f["run"]
    workspace = root / "batch-runner/workspace"
    if condition == "codex":
        _runtime_paths(root, monkeypatch)
        step1.prepare_tasks(str(root / writer.CONFIG_PATH))  # Real model-free legacy writer.
    assert preparer.verify_runtime_checkout(
        checkout=root, run_id=run.run_id, condition=condition, expected_reviewed_source_sha=f["anchor"],
    ) == f["marker"]
    events = []
    _provider_boundaries(monkeypatch, events)
    for name in ("COMPARISON_LAUNCH_ENABLED", "GPT54_COMPARISON_LAUNCH_ENABLED"):
        monkeypatch.setenv(name, "true")
    monkeypatch.setenv("EXPECTED_REVIEWED_SOURCE_SHA", f["anchor"])
    monkeypatch.setenv("COMPARISON_MANIFEST_PATH", _PROSPECTIVE_MANIFEST)
    real_lineage = preparer.verify_runtime_checkout
    real_binding = writer._binding if condition == "codex" else v2_capture._binding

    def observed_lineage(**kwargs):
        assert kwargs == {"checkout": root, "run_id": run.run_id, "condition": condition}
        result = real_lineage(**kwargs)
        assert result == f["marker"]
        events.append("historical_default_lineage")
        return result

    def observed_binding(*args, **kwargs):
        result = real_binding(*args, **kwargs)
        events.append("input_binding")
        return result

    def no_capture(*args, **kwargs):
        pytest.fail("refused runtime attempted capture publication")

    monkeypatch.setattr(preparer, "verify_runtime_checkout", observed_lineage)
    monkeypatch.setattr(writer if condition == "codex" else v2_capture, "_binding", observed_binding)
    monkeypatch.setattr(writer, "_write_no_clobber", no_capture)
    before = _tree_snapshot(tmp_path)
    f["git_calls"].clear()
    if condition == "codex":
        with pytest.raises(writer.ComparisonRuntimeLaunchRefused, match="^comparison_runtime_launch_refused$") as refusal:
            _entrypoint(condition, root, run.run_id, monkeypatch)
        assert type(refusal.value) is writer.ComparisonRuntimeLaunchRefused
        assert (root / writer.CAPTURE_PATH).read_bytes() == _json(f["captures"][f["index"]])
    else:
        assert _entrypoint(condition, root, run.run_id, monkeypatch) == 1
        assert "comparison_runtime_launch_refused" in capsys.readouterr().out.splitlines()
        assert not workspace.exists()
    assert events == ["historical_default_lineage", "input_binding"]
    assert all(path == root and args in _RUNTIME_GIT for path, args in f["git_calls"])
    assert _tree_snapshot(tmp_path) == before and f["forbidden"] == []


def test_anchored_prospective_verification_does_not_wire_profile(
    tmp_path, monkeypatch, _anchored_input_seed, capsys,
):
    f = _anchored_checkout(tmp_path, monkeypatch, _anchored_input_seed)
    root, run = f["checkout"], f["run"]
    assert preparer.verify_runtime_checkout(
        checkout=root, run_id=run.run_id, condition=run.condition, expected_reviewed_source_sha=f["anchor"],
    ) == f["marker"]
    events = []
    _provider_boundaries(monkeypatch, events)
    monkeypatch.setenv("EXPECTED_REVIEWED_SOURCE_SHA", f["anchor"])
    monkeypatch.setenv("COMPARISON_MANIFEST_PATH", f["manifest_path"])
    real_lineage = preparer.verify_runtime_checkout

    def historical_only(**kwargs):
        assert kwargs == {"checkout": root, "run_id": run.run_id, "condition": run.condition}
        events.append("historical_default")
        return real_lineage(**kwargs)

    monkeypatch.setattr(preparer, "verify_runtime_checkout", historical_only)
    before = _tree_snapshot(tmp_path)
    assert _entrypoint(run.condition, root, run.run_id, monkeypatch) == 1
    assert "comparison_runtime_launch_refused" not in capsys.readouterr().out.splitlines()
    assert events == ["historical_default"]  # Source refusal, not a capture or launch-guard success.
    assert not (root / writer.CAPTURE_PATH).exists()
    assert _tree_snapshot(tmp_path) == before and f["forbidden"] == []
