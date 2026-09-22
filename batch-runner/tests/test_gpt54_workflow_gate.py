"""One offline selector for workflow admission and prepared-checkout bindings."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

import gpt54_comparison_preflight as preflight
import gpt54_disposable_checkout as preparer
import gpt54_run_config_bundle as config_bundle
import gpt54_run_input_bundle as input_bundle
import gpt54_workflow_gate as gate
from .test_gpt54_disposable_checkout import (
    _allow_only_temporary_git, _commit_fixture, _fixture_git, _sidecars, _source_state,
    _step0_manifest_checkout,
)
from .test_gpt54_prepared_input_attestation import _bundle_fixture, _json, _step0_manifest_source, _tree_snapshot
from .test_gpt54_run_input_bundle import _copy_files, _input_bundle_seed, _snapshot_files


_OWNERS = {"sandbox_v2": "agentic-v2-stage-run", "codex": "batch-run"}


@pytest.mark.parametrize("case", ["api", "cli", "missing_argument"])
def test_step0_manifest_workflow_helper_forwards_explicit_source(
    case, _step0_manifest_checkout, monkeypatch, capsys,
):
    fixture = _step0_manifest_checkout
    inputs, run = fixture["inputs"], fixture["run"]
    repository, sha = fixture["repository"], fixture["reviewed_sha"]
    monkeypatch.setattr(gate, "ROOT", repository)
    request = _request("codex", _inputs("codex", run.run_id, sha), sha)
    kwargs = {
        "repository": repository, "destination": fixture["destination"],
        "manifest": inputs["manifest"], "combined_plan": inputs["combined_plan"],
        "dataset_parquet": inputs["dataset_parquet"], "reference_root": inputs["reference_root"],
        "step0_manifest": None if case == "missing_argument" else fixture["step0_manifest"],
    }
    if case == "missing_argument":
        before = _tree_snapshot(repository.parent)
        with pytest.raises(gate.WorkflowExecutionRefused, match="Step 0 manifest"):
            gate.prepare_workflow_execution(request, **kwargs)
        assert _tree_snapshot(repository.parent) == before
        assert not fixture["destination"].exists()
        return
    if case == "cli":
        capsys.readouterr()
        assert gate.main([
            "--workflow", "batch-run", "--inputs-json", request.inputs_json,
            "--event-name", "workflow_dispatch", "--event-ref", "refs/heads/main",
            "--event-sha", sha, "--workflow-sha", sha,
            "--repository", str(repository), "--destination", str(fixture["destination"]),
            "--dataset-parquet", str(inputs["dataset_parquet"]), "--reference-root", str(inputs["reference_root"]),
            "--step0-manifest", str(fixture["step0_manifest"]),
        ]) == 2  # Local preparation does not waive the launch gate.
        evidence, refusal = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        assert refusal["launch_allowed"] is False and "launch flags are false" in refusal["error"]
    else:
        prepared = gate.prepare_workflow_execution(request, **kwargs)
        evidence = gate.verify_workflow_execution(
            prepared, manifest=inputs["manifest"], combined_plan=inputs["combined_plan"],
        )
    assert evidence["commands_executed"] is False
    assert evidence["launch_allowed"] is evidence["dispatch_launch_allowed"] is False
    assert (fixture["destination"] / input_bundle.STEP0_MANIFEST_PATH).read_bytes() == fixture["step0_manifest"].read_bytes()


_INPUT_DIGESTS = {
    "sandbox_v2": "0c89c66074686e4d92dfe3b7f5c3d6d8bf993d4068fd0882b22c7d2c872529fc",
    "codex": "ec68ac701575dc8bd0e79620b6a4139a9b2bc938cc5902fa8467c612460708fb",
}
# Canonical YAML projections of the legacy steps on immutable main 1671d6d8.
# Only forwarding the new empty input is removed before the batch comparison.
_LEGACY_STEPS = {
    "sandbox_v2": {
        "free": "5d9c4fc69d0cf5cd18818ae3a62558e0f7e808475af39ef2100e1310a1c2363c",
        "paid": "367101fbff58aa485984ff9a855af2bdfd4b92d8c0d2e6ed59fca8a82c39f94e",
        "collect": "576f3f12f6e2796fc5b3e2325a32d49066038fd20f71d3c598f009aa4183703d",
    },
    "codex": {
        "inspect-mode": "8cde7f5a0d214b6cb776a4391db7e5c9f91294d8255752c9ddd517245d3f3e9c",
        "reject-agentic": "61f103b796bfcf1ed4839b64f098314a5ffa927fdb154da1961370402009eb46",
        "reject-unconfirmed-codex": "66ca90357752778648049e1dfb61a8703e1ce3d9a75e3edcb3bbc650becd2034",
        "batch-run": "be941a3c692d20febe33ccd639178ae25c8ced51617f739feb254a3fde1a5e16",
    },
}
_REFUSALS = (
    "destination_exists", "destination_symlink", "destination_escape", "source_head",
    "ready_missing", "ready_altered", "ready_noncanonical", "ready_symlink",
    "reservation_missing", "reservation_altered", "config_missing", "config_altered",
    "input_missing", "input_altered", "quarantine", "head_attached", "head_wrong",
    "head_moves", "wrong_run", "wrong_condition", "combined_launch_enabled",
    "preparation_failure", "rerun", "source_cwd", "changed_argv", "source_pin_missing",
    "source_pin_changed", "ready_hardlink", "handoff_failure",
)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _inputs(condition: str, run_id: str, sha: str) -> dict[str, Any]:
    if condition == "sandbox_v2":
        return {
            "stage": "advance_check_5", "mode": "paid", "isolation": "same-host",
            "plan": "experiments/execution_envelope/agentic_corrected_harness_plan.yaml",
            "run_id": run_id, "resume_from_github_run": "",
            "comparison_reviewed_source_sha": sha,
        }
    return {
        "experiment_yaml": "execution_envelope/" + run_id, "experiment_name": "",
        "dry_run": False, "relay_run": 0, "relay_lineage_id": "", "source_sha": "",
        "wall_timeout": 290, "sandbox_image_digest": "", "codex_foundry_confirmed": True,
        "comparison_reviewed_source_sha": sha,
    }


def _request(condition: str, values: dict[str, Any], sha: str, **changes: Any) -> Any:
    context = {
        "event_name": "workflow_dispatch", "event_ref": "refs/heads/main",
        "event_sha": sha, "workflow_sha": sha, **changes,
    }
    return gate.request_from_inputs(_OWNERS[condition], values, **context)


@pytest.fixture(scope="module")
def _workflow_prepared_seed(tmp_path_factory: Any, _input_bundle_seed: Any) -> Any:
    """Run real preparation once per ABBA recipe; freeze the generated bytes.

    Mutation cases copy generated bytes into their own real linked worktree.
    No Git metadata or mutable checkout is shared, and no verdict is cached. The saved
    ordering trace comes from actual preparation and lineage calls for that run.
    """
    root = tmp_path_factory.mktemp("workflow-prepared-seed")
    seeds = []
    with pytest.MonkeyPatch.context() as setup:
        forbidden, _ = _allow_only_temporary_git(setup, root)
        _input_bundle_seed.install(setup)
        oracle = root / "oracle"
        oracle.mkdir()
        inputs, _, _, _, _ = _input_bundle_seed.inputs(oracle, setup, "identical")
        plan = _input_bundle_seed.plan
        repository = root / "source"
        _bundle_fixture(repository, manifest=inputs["manifest"], combined_plan=inputs["combined_plan"],
                        run=plan.dispatch.runs[0], materialize=False)
        (repository / "ordinary-note.txt").write_bytes(b"reviewed bytes\n")
        _fixture_git(repository, "init", "--quiet", "--initial-branch=fixture-main",
                     "--object-format=sha1", "--template=")
        reviewed_sha = _commit_fixture(repository, "Reviewed temporary workflow source")
        setup.setattr(preparer, "TRUSTED_ROOT", repository)
        setup.setattr(gate, "ROOT", repository)
        real_prepare, real_lineage = gate.prepare_disposable_checkout, gate.verify_runtime_checkout
        order = []

        def observed_prepare(*args: Any, **kwargs: Any) -> Any:
            order.append("prepare")
            result = real_prepare(*args, **kwargs)
            order.append("prepared")
            return result

        def observed_lineage(*args: Any, **kwargs: Any) -> Any:
            order.append("lineage")
            return real_lineage(*args, **kwargs)

        setup.setattr(gate, "prepare_disposable_checkout", observed_prepare)
        setup.setattr(gate, "verify_runtime_checkout", observed_lineage)
        tracked = {*inputs["manifest"]["source_pins"], config_bundle.MANIFEST_PATH, "ordinary-note.txt"}
        for run in plan.dispatch.runs:
            order.clear()
            checkout = root / run.run_id
            request = _request(run.condition, _inputs(run.condition, run.run_id, reviewed_sha), reviewed_sha)
            prepared = gate.prepare_workflow_execution(
                request, repository=repository, destination=checkout,
                manifest=inputs["manifest"], combined_plan=inputs["combined_plan"],
                dataset_parquet=inputs["dataset_parquet"], reference_root=inputs["reference_root"],
                step0_manifest=_step0_manifest_source(inputs, run),
            )
            reservation, quarantine = _sidecars(checkout)
            assert not quarantine.exists()
            files = tuple((name, data) for name, data in _snapshot_files(checkout)
                          if name != ".git" and name not in tracked)
            seeds.append((prepared, files, reservation.read_bytes(), tuple(order)))
        assert forbidden == []
    original = _tree_snapshot(root)
    yield tuple(seeds)
    assert _tree_snapshot(root) == original


def _copy_prepared_workflow(
    seed: Any, *, request: Any, repository: Path, checkout: Path, order: list[str],
) -> Any:
    """Copy a real prepared fixture without copying its linked-worktree metadata."""
    prepared, files, reservation_bytes, observed_order = seed
    assert prepared.request == request
    checkout.mkdir()
    _fixture_git(repository, "worktree", "add", "--detach", "--", str(checkout), request.reviewed_source_sha)
    _copy_files(checkout, files)
    reservation, _ = _sidecars(checkout)
    _copy_files(reservation.parent, ((reservation.name, reservation_bytes),))
    # Keep the real seed's preparation-order evidence, not synthetic callbacks.
    order.extend(observed_order)
    return replace(prepared, repository=repository, checkout=checkout,
                   cwd=checkout / prepared.cwd.relative_to(prepared.checkout))


def _job_if(expression: str, values: dict[str, Any], *, inspected: str = "success") -> bool:
    """Evaluate only the small boolean vocabulary used by these static job guards."""
    text = expression.removeprefix("${{").removesuffix("}}").strip()
    for source, target in (
        ("needs.inspect-mode.result", "inspected"),
        ("needs.inspect-mode.outputs.uses_agentic", "agentic"),
        ("needs.inspect-mode.outputs.codex_blocked", "blocked"),
        ("needs.free.result", "inspected"),
    ):
        text = text.replace(source, target)
    text = re.sub(r"!(?!=)", "not ", text.replace("&&", " and ").replace("||", " or ")).strip()
    tree = ast.parse(text, mode="eval")
    allowed = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
               ast.Compare, ast.Eq, ast.NotEq, ast.Call, ast.Name, ast.Attribute,
               ast.Load, ast.Constant)
    assert all(isinstance(node, allowed) for node in ast.walk(tree))
    assert all(isinstance(node.func, ast.Name) and node.func.id in {"contains", "always"}
               for node in ast.walk(tree) if isinstance(node, ast.Call))
    return bool(eval(compile(tree, "<workflow condition>", "eval"), {"__builtins__": {}}, {
        "inputs": SimpleNamespace(**values), "inspected": inspected,
        "agentic": "false", "blocked": "false", "always": lambda: True,
        "contains": lambda value, part: part.lower() in value.lower(),
    }))


def _workflow_contract(condition: str, monkeypatch: Any) -> None:
    from . import test_a_batch_dispatch_can_open_the_codex_gate as batch_cases
    from . import test_agentic_workflows as workflow_cases

    owner = _OWNERS[condition]
    path = preflight.ROOT / ".github/workflows" / (owner + ".yml")
    workflow = yaml.safe_load(path.read_bytes())
    dispatch = workflow[True]["workflow_dispatch"]["inputs"]
    legacy_inputs = deepcopy(dispatch)
    added = legacy_inputs.pop("comparison_reviewed_source_sha")
    assert added["type"] == "string" and added["required"] is False and added["default"] == ""
    assert _digest(legacy_inputs) == _INPUT_DIGESTS[condition]
    for name, digest in _LEGACY_STEPS[condition].items():
        steps = deepcopy(workflow["jobs"][name]["steps"])
        if name == "batch-run":
            relay = next(step for step in steps if step.get("name") == "Retrigger relay run")
            relay["run"] = relay["run"].replace(
                ' \\\n  -f comparison_reviewed_source_sha="$COMPARISON_REVIEWED_SOURCE_SHA_INPUT"', "",
            )
        assert _digest(steps) == digest

    admission = workflow["jobs"]["comparison-admission"]
    assert admission["permissions"] == {"contents": "read"}
    assert admission["timeout-minutes"] == 10
    assert "needs" not in admission and "outputs" not in admission
    text = _json(admission).decode()
    assert all(token not in text for token in (
        "secrets.", "id-token", "azure/login", "continue-on-error", "always()",
        "snapshot_download", "gh workflow", "--no-verify", "worktree remove",
    ))
    steps = admission["steps"]
    assert len(steps) == 5
    bind, checkout, python_setup, install, prepare = steps
    assert bind["env"]["REVIEWED_SOURCE_SHA"] == "${{ inputs.comparison_reviewed_source_sha }}"
    for check in (
        '[[ "$GITHUB_EVENT_NAME" == \'workflow_dispatch\' ]]',
        '[[ "$GITHUB_REF" == \'refs/heads/main\' ]]',
        '[[ "$REVIEWED_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]',
        '[[ "$GITHUB_SHA" == "$REVIEWED_SOURCE_SHA" ]]',
        '[[ "$WORKFLOW_SHA" == "$REVIEWED_SOURCE_SHA" ]]',
    ):
        assert check in bind["run"]
    assert checkout["with"] == {
        "ref": "${{ inputs.comparison_reviewed_source_sha }}", "persist-credentials": False,
    }
    assert "actions/setup-python@" in python_setup["uses"]
    assert "requirements.txt" not in install["run"]
    assert prepare["env"]["COMPARISON_INPUTS"] == "${{ toJSON(inputs) }}"
    command = prepare["run"]
    for piece in (
        "env -u PYTHONPATH python3 -I batch-runner/gpt54_workflow_gate.py",
        "--workflow " + owner + ' --inputs-json "$COMPARISON_INPUTS"',
        '--repository "$GITHUB_WORKSPACE"',
        '--destination "$RUNNER_TEMP/comparison-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"',
        '--dataset-parquet "$GITHUB_WORKSPACE/data/gdpval-local/data/train-00000-of-00001.parquet"',
        '--reference-root "$GITHUB_WORKSPACE/data/gdpval-local"',
    ):
        assert piece in command
    assert not any("${{ inputs." in step.get("run", "") for step in steps)
    assert not any(token in command for token in ("eval ", "--shard", "--wall-timeout", "|| true"))

    sha = "d" * 40
    run_id = "gpt54_v2_codex_v1_" + ("v2" if condition == "sandbox_v2" else "codex") + "_r1"
    values = _inputs(condition, run_id, sha)
    assert _request(condition, values, sha).run_id == run_id
    legacy_job = workflow["jobs"]["free" if condition == "sandbox_v2" else "inspect-mode"]
    variants = [values, {**values, "comparison_reviewed_source_sha": ""}]
    for bad_sha in ("main", "v1", sha[:12], sha.upper(), " " + sha, None, False, 123):
        altered = {**values, "comparison_reviewed_source_sha": bad_sha}
        with pytest.raises(ValueError):
            _request(condition, altered, sha)
    for context in ({"event_sha": "a" * 40}, {"workflow_sha": "a" * 40},
                    {"event_name": "push"}, {"event_ref": "refs/heads/other"}):
        with pytest.raises(ValueError):
            _request(condition, values, sha, **context)
    run_key = "run_id" if condition == "sandbox_v2" else "experiment_yaml"
    other = "gpt54_v2_codex_v1_" + ("codex" if condition == "sandbox_v2" else "v2") + "_r1"
    if condition == "codex":
        other = "execution_envelope/" + other
    for value in (other, values[run_key] + "-shard-1-of-1", "ordinary", "../" + values[run_key]):
        altered = {**values, run_key: value}
        variants.append(altered)
        with pytest.raises(ValueError):
            _request(condition, altered, sha)
    for key in values:
        altered = deepcopy(values)
        del altered[key]
        with pytest.raises(ValueError):
            _request(condition, altered, sha)
    with pytest.raises(ValueError):
        _request(condition, {**values, "launch_override": True}, sha)
    overrides = ({"stage": "full_220", "mode": "dry-run", "isolation": "fixture",
                  "plan": "comparison-run.json", "resume_from_github_run": "123"}
                 if condition == "sandbox_v2" else
                 {"relay_run": 1, "source_sha": sha, "relay_lineage_id": "old-run",
                  "wall_timeout": 0, "sandbox_image_digest": "sha256:changed",
                  "experiment_name": "overridden", "dry_run": True,
                  "codex_foundry_confirmed": False})
    for key, value in overrides.items():
        with pytest.raises(ValueError):
            _request(condition, {**values, key: value}, sha)
    for altered in variants:
        assert _job_if(admission["if"], altered)
        assert not _job_if(legacy_job["if"], altered)
        if condition == "sandbox_v2":
            assert not _job_if(workflow["jobs"]["paid"]["if"], altered, inspected="skipped")
            assert not _job_if(workflow["jobs"]["collect"]["if"], altered, inspected="skipped")
        else:
            assert not _job_if(workflow["jobs"]["batch-run"]["if"], altered, inspected="skipped")
    ordinary = {name: row.get("default", "") for name, row in dispatch.items()}
    if condition == "codex":
        ordinary["experiment_yaml"] = "exp033_codex_foundry_fixed5"
    assert not _job_if(admission["if"], ordinary)
    assert _job_if(legacy_job["if"], ordinary)
    if condition == "codex":
        workflow_cases.test_general_batch_blocks_agentic_before_any_credential_step()
        batch_cases.test_the_credentialed_job_does_not_start_at_all(workflow)
        batch_cases.test_the_relay_forwards_every_input_it_was_given(workflow, dispatch)
    # Workflow orchestration and the imported gate itself are sealed sources,
    # not untracked dependencies of the already sealed Python compiler.
    manifest = preflight.load_plan()
    for name in (".github/workflows/agentic-v2-stage-run.yml", ".github/workflows/batch-run.yml",
                 "batch-runner/gpt54_workflow_gate.py"):
        for change in ("missing", "digest"):
            altered = deepcopy(manifest)
            if change == "missing":
                del altered["source_pins"][name]
            else:
                altered["source_pins"][name] = "0" * 64
            with pytest.raises(preflight.DispatchPlanRefused):
                preflight.compile_dispatch_plan(altered)
    sol = yaml.safe_load((preflight.ROOT / preflight.ENVELOPE / "gpt56_sol_foundry_codex_pilot.yaml").read_bytes())
    for name, digest in sol["source_pins"].items():
        assert hashlib.sha256((preflight.ROOT / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize(("condition", "case"), [
    ("sandbox_v2", "workflow"), ("codex", "workflow"),
    ("sandbox_v2", "r1"), ("codex", "r1"), ("codex", "r2"), ("sandbox_v2", "r2"),
    *((condition, case) for condition in ("sandbox_v2", "codex") for case in _REFUSALS),
])
def test_workflow_execution_gate(
    condition: str, case: str, tmp_path: Path, monkeypatch: Any, capsys: Any, _input_bundle_seed: Any,
    request: Any,
) -> None:
    # Input-shape/YAML checks do not create a prepared fixture. Resolve the
    # module seed before installing per-case subprocess guards, never through
    # a patched runtime helper. CLI and preparation/handoff failures stay real.
    seeds = request.getfixturevalue("_workflow_prepared_seed") if case != "workflow" else None
    forbidden, git_calls = _allow_only_temporary_git(monkeypatch, tmp_path)
    _input_bundle_seed.install(monkeypatch)
    if case == "workflow":
        _workflow_contract(condition, monkeypatch)
        assert forbidden == git_calls == []
        return

    oracle_root = tmp_path / "input-oracle"
    oracle_root.mkdir()
    inputs, _, _, _, _ = _input_bundle_seed.inputs(oracle_root, monkeypatch, "identical")
    plan = _input_bundle_seed.plan
    index = (2 if case == "r2" else 1) if condition == "codex" else (3 if case == "r2" else 0)
    run = plan.dispatch.runs[index]
    repository, checkout = tmp_path / "source", tmp_path / "prepared"
    _bundle_fixture(repository, manifest=inputs["manifest"], combined_plan=inputs["combined_plan"],
                    run=run, materialize=False)
    note = repository / "ordinary-note.txt"
    note.write_bytes(b"reviewed bytes\n")
    _fixture_git(repository, "init", "--quiet", "--initial-branch=fixture-main",
                 "--object-format=sha1", "--template=")
    reviewed_sha = _commit_fixture(repository, "Reviewed temporary workflow source")
    note.write_bytes(b"uncommitted caller bytes\n")
    source_before, oracle_before = _source_state(repository), _tree_snapshot(oracle_root)
    monkeypatch.setattr(preparer, "TRUSTED_ROOT", repository)
    monkeypatch.setattr(gate, "ROOT", repository)
    order = []
    real_prepare, real_lineage = gate.prepare_disposable_checkout, gate.verify_runtime_checkout

    def observed_prepare(*args: Any, **kwargs: Any) -> Any:
        order.append("prepare")
        result = real_prepare(*args, **kwargs)
        order.append("prepared")
        return result

    def observed_lineage(*args: Any, **kwargs: Any) -> Any:
        order.append("lineage")
        return real_lineage(*args, **kwargs)

    monkeypatch.setattr(gate, "prepare_disposable_checkout", observed_prepare)
    monkeypatch.setattr(gate, "verify_runtime_checkout", observed_lineage)
    request = _request(condition, _inputs(condition, run.run_id, reviewed_sha), reviewed_sha)
    kwargs = {
        "repository": repository, "destination": checkout,
        "manifest": inputs["manifest"], "combined_plan": inputs["combined_plan"],
        "dataset_parquet": inputs["dataset_parquet"], "reference_root": inputs["reference_root"],
        "step0_manifest": _step0_manifest_source(inputs, run),
    }
    validation = {key: kwargs[key] for key in ("manifest", "combined_plan")}
    if case == "destination_exists":
        checkout.mkdir()
    elif case == "destination_symlink":
        checkout.symlink_to(repository, target_is_directory=True)
    elif case == "destination_escape":
        kwargs["destination"] = tmp_path / "source" / ".." / "prepared"
    elif case == "source_head":
        request = _request(condition, _inputs(condition, run.run_id, "f" * 40), "f" * 40)
    elif case == "combined_launch_enabled":
        kwargs["combined_plan"] = {**inputs["combined_plan"], "launch_allowed": True}
    elif case in {"source_pin_missing", "source_pin_changed"}:
        changed_manifest = deepcopy(inputs["manifest"])
        pin = "batch-runner/gpt54_workflow_gate.py"
        if case == "source_pin_missing":
            del changed_manifest["source_pins"][pin]
        else:
            changed_manifest["source_pins"][pin] = "0" * 64
        kwargs["manifest"] = changed_manifest
    elif case == "preparation_failure":
        def fail_input(*args: Any, **kwargs: Any) -> None:
            raise OSError("injected offline input publication failure")
        monkeypatch.setattr(preparer, "materialize_run_input_bundle", fail_input)
    elif case == "handoff_failure":
        real_verify = gate.verify_workflow_execution

        def fail_outer_handoff(*args: Any, **kwargs: Any) -> None:
            real_verify(*args, **kwargs)
            assert (checkout / preparer.READY_PATH).is_file()
            raise gate.WorkflowExecutionRefused("injected failure after real preparation and lineage validation")

        monkeypatch.setattr(gate, "verify_workflow_execution", fail_outer_handoff)

    if case in {"destination_exists", "destination_symlink", "destination_escape", "source_head",
                "combined_launch_enabled", "preparation_failure", "source_pin_missing", "source_pin_changed",
                "handoff_failure"}:
        before = _tree_snapshot(tmp_path)
        with pytest.raises(ValueError):
            gate.prepare_workflow_execution(request, **kwargs)
        if case in {"preparation_failure", "handoff_failure"}:
            reservation, quarantine = _sidecars(checkout)
            assert reservation.is_file() and quarantine.is_file()
            assert (checkout / preparer.READY_PATH).exists() is (case == "handoff_failure")
            expected_phase = "input_bundle" if case == "preparation_failure" else "workflow_handoff"
            assert json.loads(quarantine.read_bytes())["phase"] == expected_phase
            with pytest.raises(preparer.DisposableCheckoutRefused, match="quarantined"):
                preparer.verify_runtime_checkout(checkout=checkout, run_id=run.run_id, condition=condition)
            retained = _tree_snapshot(tmp_path)
            with pytest.raises(ValueError):
                gate.prepare_workflow_execution(request, **kwargs)
            assert _tree_snapshot(tmp_path) == retained
        else:
            assert _tree_snapshot(tmp_path) == before
    else:
        if case == "r2":
            preparations = []
            real_workflow_prepare = gate.prepare_workflow_execution

            def observed_workflow_prepare(*args: Any, **kwargs: Any) -> Any:
                result = real_workflow_prepare(*args, **kwargs)
                preparations.append(result)
                return result

            monkeypatch.setattr(gate, "prepare_workflow_execution", observed_workflow_prepare)
            assert gate.main([
                "--workflow", _OWNERS[condition], "--inputs-json", request.inputs_json,
                "--event-name", "workflow_dispatch", "--event-ref", "refs/heads/main",
                "--event-sha", reviewed_sha, "--workflow-sha", reviewed_sha,
                "--repository", str(repository), "--destination", str(checkout),
                "--dataset-parquet", str(inputs["dataset_parquet"]),
                "--reference-root", str(inputs["reference_root"]),
                *(["--step0-manifest", str(_step0_manifest_source(inputs, run))] if condition == "codex" else []),
            ]) == 2
            documents = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
            assert len(documents) == 2 and len(preparations) == 1
            assert documents[0]["commands_executed"] is False
            assert documents[1]["launch_allowed"] is False and "launch" in documents[1]["error"]
            prepared = preparations[0]
        else:
            prepared = _copy_prepared_workflow(
                seeds[index], request=request, repository=repository, checkout=checkout, order=order,
            )
        assert order[:3] == ["prepare", "prepared", "lineage"]
        reservation, quarantine = _sidecars(checkout)
        ready = checkout / preparer.READY_PATH
        gitdir = Path(os.fsdecode(_fixture_git(
            checkout, "rev-parse", "--absolute-git-dir",
        ).stdout.rstrip(b"\n")))
        head = gitdir / "HEAD"
        if case == "rerun":
            before = _tree_snapshot(tmp_path)
            with pytest.raises(ValueError):
                gate.prepare_workflow_execution(request, **kwargs)
            assert _tree_snapshot(tmp_path) == before
        else:
            paths = {"ready": ready, "reservation": reservation,
                     "config": checkout / config_bundle.READY_PATH,
                     "input": checkout / input_bundle.READY_PATH}
            if case.endswith("_missing"):
                paths[case.removesuffix("_missing")].unlink()
            elif case.endswith("_altered"):
                target = paths[case.removesuffix("_altered")]
                target.write_bytes(_json({**json.loads(target.read_bytes()), "forged": True}))
            elif case == "ready_noncanonical":
                ready.write_bytes(ready.read_bytes() + b"\n")
            elif case == "ready_symlink":
                moved = tmp_path / "moved-ready"
                ready.rename(moved)
                ready.symlink_to(moved)
            elif case == "ready_hardlink":
                os.link(ready, tmp_path / "ready-alias")
            elif case == "quarantine":
                quarantine.write_bytes(b"{}")
            elif case == "head_attached":
                head.write_bytes(b"ref: refs/heads/fixture-main\n")
            elif case == "head_wrong":
                head.write_bytes(b"f" * 40 + b"\n")
            elif case == "head_moves":
                real_marker = preparer._marker
                def move_head(*args: Any, **kwargs: Any) -> Any:
                    result = real_marker(*args, **kwargs)
                    head.write_bytes(b"f" * 40 + b"\n")
                    return result
                monkeypatch.setattr(preparer, "_marker", move_head)
            elif case == "wrong_run":
                prepared = replace(prepared, request=replace(request, run_id=plan.dispatch.runs[3 - index].run_id))
            elif case == "wrong_condition":
                prepared = replace(prepared, request=replace(request, condition="codex" if condition == "sandbox_v2" else "sandbox_v2"))
            elif case == "source_cwd":
                prepared = replace(prepared, cwd=repository / run.working_directory)
            elif case == "changed_argv":
                prepared = replace(prepared, commands=(run.commands[0] + ("--dry-run",),))
            if case in {"r1", "r2"}:
                before = _tree_snapshot(tmp_path)
                evidence = gate.verify_workflow_execution(prepared, **validation)
                assert evidence["launch_allowed"] is evidence["full_220_allowed"] is False
                assert str(checkout / run.working_directory) in _json(evidence).decode()
                assert evidence["commands"] == [list(command) for command in run.commands]
                with pytest.raises(ValueError, match="launch"):
                    gate.require_workflow_launch(prepared, **validation)
                assert _tree_snapshot(tmp_path) == before
                assert not quarantine.exists()  # False launch flags are not failed materialization.
                assert head.read_bytes() == reviewed_sha.encode() + b"\n"
                assert json.loads(ready.read_bytes())["abba_index"] == index
                assert len(inputs["manifest"]["source_pins"]) == 37
                assert {".github/workflows/agentic-v2-stage-run.yml", ".github/workflows/batch-run.yml",
                        "batch-runner/gpt54_workflow_gate.py"} <= preflight.REQUIRED_SOURCES
                inspection = preflight.inspect_plan(inputs["manifest"], grading_plan=inputs["combined_plan"])
                assert inspection["configuration_valid"] is True
                assert inspection["workflow_execution_gate"]["permissions"] == {"contents": "read"}
                assert inspection["launch_allowed"] is inspection["full_220_allowed"] is False
            else:
                with pytest.raises(ValueError):
                    gate.verify_workflow_execution(prepared, **validation)
    assert _source_state(repository) == source_before
    assert _tree_snapshot(oracle_root) == oracle_before
    assert forbidden == []
