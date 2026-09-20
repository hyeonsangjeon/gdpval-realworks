"""One offline selector for inert pilot recipes and explicit preflight consumption."""

import builtins
import hashlib
import json
import os
from functools import lru_cache

import pytest
import yaml

# Capture the real class before the inherited guards prohibit construction.
import step8_grade as step8
import gpt56_foundry_evidence_intake as evidence
import gpt56_pilot_identity_plan as identity
import gpt56_sol_codex_pilot_preflight as pilot
from core.execution_envelope_tasks import load_task_catalog, select_advance_check_tasks
from .test_gpt56_evidence_preflight_gate import (
    ALL_BLOCKERS, CLEARED, REMAINING, _expected_legacy, published_seed,
)
from .test_gpt56_foundry_evidence_intake import (
    AS_OF, OPTIONS, REVIEWED, _json, _offline, _parse_cache, _seed, _tree,
)
from .test_gpt56_sol_codex_pilot_preflight import offline_only

TASK_IDS = [
    "02aa1805-c658-4069-8a6a-02dec146063a",
    "0112fc9b-c3b2-4084-8993-5a4abb1f54f1",
    "2ea2e5b5-257f-42e6-a7dc-93763f28b19d",
    "3baa0009-5a60-4ae8-ae99-4955cb328ff3",
    "0818571f-5ff7-4d39-9d2c-ced5ae44299e",
]
IDENTITY_BLOCKER = "pilot_dispatch_and_grading_identity_not_wired"
SENTINEL = "private-untrusted-value-DO-NOT-ECHO"


def _copy(files, root):
    for name, data in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        assert path.stat().st_nlink == 1 and not path.is_symlink()


def _reservation(root):
    return root.with_name(root.name + identity.RESERVATION_SUFFIX)


def _set(document, keys, value):
    for key in keys[:-1]:
        document = document[key]
    document[keys[-1]] = value


def _field_names(value):
    if isinstance(value, dict):
        return set(value) | {name for child in value.values() for name in _field_names(child)}
    if isinstance(value, list):
        return {name for child in value for name in _field_names(child)}
    return set()


@pytest.fixture(autouse=True)
def _no_execution(_offline, monkeypatch, offline_only):
    def forbidden(*args, **kwargs):
        offline_only.append("grader/runtime boundary")
        raise AssertionError("identity compiler attempted execution")

    monkeypatch.setattr(step8.Grader, "__init__", forbidden)
    for name in ("RubricLoader", "main", "preflight_routes", "open_cost_recorder"):
        monkeypatch.setattr(step8, name, forbidden)


@pytest.fixture
def plan():
    return pilot.load_plan(pilot.PLAN)


@pytest.fixture(scope="module")
def identity_seeds(tmp_path_factory, published_seed):
    """Real publication once per evidence mode; only immutable bytes are shared."""
    @lru_cache(maxsize=2)
    def prepare(linked=False):
        parent = tmp_path_factory.mktemp("pilot-identity-seed")
        options = {}
        if linked:
            _copy(published_seed(), parent)
            options = {"evidence_bundle": parent / "bundle", **OPTIONS}
        result = identity.publish_pilot_identity(
            pilot.load_plan(pilot.PLAN), destination=parent / "identity", **options,
        )
        assert (parent / "identity" / identity.PLAN_PATH).read_bytes() == result.canonical_bytes()
        return _tree(parent)
    return prepare


@pytest.fixture
def sealed(tmp_path, identity_seeds, _no_execution):
    _copy(identity_seeds(), tmp_path)
    return tmp_path / "identity"


@pytest.fixture
def linked(tmp_path, identity_seeds, _no_execution):
    _copy(identity_seeds(True), tmp_path)
    return tmp_path / "identity", {"evidence_bundle": tmp_path / "bundle", **OPTIONS}


def test_canonical_recipes_bind_the_real_grader_and_exact_five_tasks(plan, monkeypatch):
    calls = []
    for name in ("validate_grading_config", "compute_grader_source_hash"):
        real = getattr(step8, name)

        def tracked(*args, _name=name, _real=real, **kwargs):
            calls.append(_name)
            return _real(*args, **kwargs)

        monkeypatch.setattr(step8, name, tracked)
    compiled = identity.compile_pilot_identity(plan)
    assert calls == ["validate_grading_config", "compute_grader_source_hash"]
    document = compiled.as_dict()
    assert compiled.canonical_bytes() == _json(document)
    assert compiled.sha256 == hashlib.sha256(compiled.canonical_bytes()).hexdigest()
    assert document["evidence_linkage"] is None
    assert document["contract_sha256"] == pilot.seal(plan)
    assert document["source_pins"] == plan["source_pins"]
    assert set(plan["source_pins"]) == pilot.REQUIRED_SOURCES and len(pilot.REQUIRED_SOURCES) == 46
    assert document["dataset"] == plan["dataset"]
    assert document["launch_allowed"] is document["full_220_allowed"] is False
    assert document["evidence_boundary"] == "offline_dispatch_grading_identity"
    dispatch, grading = document["dispatch"], document["grading"]
    catalog = load_task_catalog()
    assert list(select_advance_check_tasks(catalog).task_ids) == TASK_IDS
    for section in (dispatch, grading):
        assert section["run_id"] == "gpt56_sol_foundry_codex_pilot5_v1"
        assert section["condition"] == "codex_foundry" and section["repeat"] == 1
        assert section["task_ids"] == TASK_IDS and section["expected_task_count"] == 5
        assert section["ordered_task_ids_sha256"] == step8._ordered_task_ids_sha256(TASK_IDS)
    assert _json(dispatch["tasks"]) == _json(grading["tasks"])
    for row in dispatch["tasks"]:
        task = catalog.by_task_id()[row["task_id"]]
        assert row["prompt_sha256"] == task.prompt_sha256
        assert row["reference_files"] == [
            {"path": role, "sha256": plan["dataset"]["input_file_versions"][role]}
            for role in task.reference_file_paths
        ]
    assert dispatch["identity"]["provider"] == "azure"
    assert dispatch["identity"]["model"] == "gpt-5.6-sol"
    assert dispatch["identity"]["fast_mode"] is False
    assert dispatch["identity"]["fallbacks"] == []
    assert dispatch["foundry_route"]["provider_id"] == "gdpval-foundry"
    assert dispatch["foundry_route"]["auth_module"] == "core.codex_azure_token"
    assert dispatch["codex_request"] == {"reasoning_effort": "max", "model_context_window": 1000000}
    assert dispatch["logical_attempts_per_task"] == dispatch["pilot_controls"]["repeats"] == 1
    assert dispatch["pilot_controls"]["fresh_session_per_attempt"] is True
    assert dispatch["pilot_controls"]["relay_max_runs"] == 0
    assert dispatch["pilot_controls"]["auto_escalation"] is False
    assert dispatch["limits"] == plan["limits"]
    assert dispatch["limits"]["timeout_seconds_per_attempt"] == 1800
    assert dispatch["limits"]["infrastructure_retries_per_task"] == 3  # After the initial attempt.
    for name in ("request_max_retries", "stream_max_retries", "resume_max_rounds"):
        assert dispatch["limits"][name] == 0
    for name in ("model_calls", "input_tokens", "output_tokens"):
        assert dispatch["limits"]["native_" + name + "_per_attempt"] is None
    assert grading["entrypoint"] == "batch-runner/step8_grade.py"
    assert grading["template"]["path"] == pilot.GRADER
    assert grading["template"]["sha256"] == plan["source_pins"][pilot.GRADER]
    assert grading["template"]["config_schema_version"] == "2.0"
    assert grading["historical_source_sha"] == "6ccd4ae346d302e3da0af455a3c5a72ec79a6984"
    assert grading["template_source_hash"] == plan["dispatch_grading_identity"]["grader_template_source_hash"]
    assert grading["rubric"]["revision"] == "11e7900cdcac61bc4daf59e65feb238acda98fbf"
    assert grading["prompt"]["version"] == "v2.2"
    assert grading["prompt"]["path"] == "batch-runner/prompts/grader_judge_v2.md"
    assert grading["prompt"]["sha256"] == plan["source_pins"][grading["prompt"]["path"]]
    assert grading["judge"] == {"model": "gpt-5.6-sol", "reasoning_effort": "max"}
    assert grading["grade_schema"]["version"] == "1.4" and grading["passes_per_task"] == 1
    assert grading["receipt_contract"] == plan["results"]
    assert grading["inference_revision"] is grading["inference_repo_id"] is None
    assert grading["runnable_config"] is grading["reuse_baseline_rerun_identity"] is False
    assert not {"argv", "command", "rerun_identity", "endpoint", "observed", "account", "deployment"} & _field_names(document)
    assert b"dc36d6837a8f0899f8bfa4d32aae9a9f6805f3b0" not in compiled.canonical_bytes()
    assert str(pilot.ROOT).encode() not in compiled.canonical_bytes()


@pytest.mark.parametrize("mode", ["compile", "publish", "verify"])
def test_cli_and_real_publication_are_deterministic_and_ready_last(plan, sealed, mode, tmp_path, monkeypatch, capsys):
    expected = identity.verify_pilot_identity(plan, bundle_root=sealed)
    target = tmp_path / "new-identity"
    writes, real = [], identity._write_no_clobber

    def tracked(path, data):
        writes.append(path.name)
        assert not (target / identity.READY_PATH).exists()
        return real(path, data)

    monkeypatch.setattr(identity, "_write_no_clobber", tracked)
    args = [] if mode == "compile" else ["--destination", str(target)] if mode == "publish" else ["--verify-bundle", str(sealed)]
    before = _tree(sealed)
    assert identity.main(args) == 0
    assert json.loads(capsys.readouterr().out) == {
        "plan_sha256": expected.sha256, "identity_complete": True,
        "evidence_boundary": identity.BOUNDARY, "launch_allowed": False, "full_220_allowed": False,
    }
    assert writes == (["new-identity" + identity.RESERVATION_SUFFIX, identity.PLAN_PATH, identity.READY_PATH]
                      if mode == "publish" else [])
    assert _tree(sealed) == before
    if mode == "publish":
        assert identity.verify_pilot_identity(plan, bundle_root=target) == expected
        assert _tree(target) == before
        assert _reservation(target).read_bytes() == _reservation(sealed).read_bytes()
        assert all(path.stat().st_nlink == 1 for path in target.iterdir())


@pytest.mark.parametrize("mode", ["absent", "null"])
def test_plan_only_bytes_remain_unchanged_without_importing_identity(plan, mode, monkeypatch, capsys):
    real = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert name != "gpt56_pilot_identity_plan", "legacy path imported the identity verifier"
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    options = {} if mode == "absent" else {"identity_bundle": None}
    assert pilot.inspect_plan(plan, **options) == _expected_legacy(plan)
    assert pilot.main([]) == 2
    assert capsys.readouterr().out == json.dumps(_expected_legacy(plan), indent=2, ensure_ascii=False) + "\n"


def test_explicit_identity_consumption_clears_only_one_blocker(plan, sealed, capsys):
    before = _tree(sealed)
    report = pilot.inspect_plan(plan, identity_bundle=sealed)
    remaining = [name for name in ALL_BLOCKERS if name != IDENTITY_BLOCKER]
    assert report["launch_blockers"] == remaining
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert report["identity_plan_gate"] == {
        "identity_complete": True,
        "consumed_plan_sha256": hashlib.sha256((sealed / identity.PLAN_PATH).read_bytes()).hexdigest(),
        "evidence_linkage": None, "cleared_blockers": [IDENTITY_BLOCKER], "remaining_blockers": remaining,
        "evidence_boundary": identity.BOUNDARY,
    }
    assert pilot.main(["--identity-bundle", str(sealed)]) == 2
    assert capsys.readouterr().out == identity._canonical_json(report) + "\n"
    assert _tree(sealed) == before


@pytest.mark.parametrize("mode", ["evidence-only", "linked", "later"])
def test_real_evidence_linkage_composes_exact_closed_gates(plan, linked, mode, monkeypatch):
    root, options = linked
    before = _tree(root.parent)
    calls, real = [], evidence.verify_foundry_evidence

    def tracked(**kwargs):
        calls.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(evidence, "verify_foundry_evidence", tracked)
    if mode == "later":
        options["as_of"] = "2026-09-20T04:00:00Z"
    report = pilot.inspect_plan(plan, **options, **({} if mode == "evidence-only" else {"identity_bundle": root}))
    assert len(calls) == (1 if mode == "evidence-only" else 2)
    remaining = REMAINING if mode == "evidence-only" else [ALL_BLOCKERS[index] for index in (4, 5, 8, 9)]
    assert report["launch_blockers"] == remaining
    assert report["evidence_gate"]["cleared_blockers"] == CLEARED
    assert report["evidence_gate"]["remaining_blockers"] == remaining
    assert report["evidence_gate"]["evaluated_at"] == options["as_of"]
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    if mode == "evidence-only":
        assert "identity_plan_gate" not in report
    else:
        gate = report["identity_plan_gate"]
        assert gate["identity_complete"] is True and gate["cleared_blockers"] == [IDENTITY_BLOCKER]
        assert gate["evidence_linkage"] == {
            "ready_bundle_sha256": hashlib.sha256((options["evidence_bundle"] / evidence.READY_PATH).read_bytes()).hexdigest(),
            "reviewed_source_sha": REVIEWED, "as_of": AS_OF,
        }
        assert gate["consumed_plan_sha256"] == hashlib.sha256((root / identity.PLAN_PATH).read_bytes()).hexdigest()
    assert not {"claims", "observed", "account", "project", "deployment", "resource_id_sha256", "endpoint"} & _field_names(report)
    assert "a" * 64 not in _json(report).decode()
    assert _tree(root.parent) == before


@pytest.mark.parametrize("keys,value", [
    (("pilot", "run_id"), "wrong-run"), (("pilot", "repeats"), 2),
    (("pilot", "relay_max_runs"), 1), (("pilot", "auto_escalation"), True),
    (("identity", "provider"), "github_copilot"), (("identity", "model"), "gpt-5.6-sol-fast"),
    (("codex_request", "reasoning_effort"), "xhigh"), (("codex_request", "model_context_window"), 999999),
    (("dataset", "tasks"), []), (("dataset", "tasks", 0, "task_id"), TASK_IDS[1]),
    (("dataset", "tasks", 0, "prompt_sha256"), "a" * 64),
    (("dataset", "revision"), "a" * 40), (("dataset", "parquet_sha256"), "a" * 64),
    (("dataset", "input_file_versions"), {}), (("grading", "template"), "../escape"),
    (("grading", "source_sha"), "a" * 40), (("grading", "rubric_revision"), "a" * 40),
    (("grading", "prompt_version"), "v1"), (("grading", "judge_model"), "gpt-5.4"),
    (("grading", "inference_revision"), "a" * 40), (("limits", "resume_max_rounds"), 1),
    (("limits", "native_model_calls_per_attempt"), 10), (("launch_enabled",), True),
    (("pilot", "full_220_enabled"), True), (("source_pins",), {}),
    (("dispatch_grading_identity", "source_base_sha"), "a" * 40),
    (("dispatch_grading_identity", "grader_template_source_hash"), "a" * 64),
])
def test_contract_drift_refuses_before_any_publication(plan, tmp_path, keys, value):
    _set(plan, keys, value)
    target = tmp_path / "absent"
    with pytest.raises(identity.PilotIdentityRefused):
        identity.publish_pilot_identity(plan, destination=target)
    assert not target.exists() and not _reservation(target).exists()


@pytest.mark.parametrize("damage", ["missing", "extra", "duplicate", "reordered"])
def test_task_membership_and_order_cannot_change(plan, damage):
    tasks = plan["dataset"]["tasks"]
    if damage == "missing":
        tasks.pop()
    elif damage == "extra":
        tasks.append({"task_id": "unregistered", "prompt_sha256": "a" * 64})
    elif damage == "duplicate":
        tasks[1] = dict(tasks[0])
    else:
        tasks.reverse()
    with pytest.raises(identity.PilotIdentityRefused):
        identity.compile_pilot_identity(plan)


@pytest.mark.parametrize("role", ["plan", "ready", "reservation"])
@pytest.mark.parametrize("damage", ["missing", "bytes", "extra-key", "noncanonical", "symlink", "hardlink"])
def test_all_published_members_are_exact_single_link_bytes(plan, sealed, tmp_path, role, damage):
    path = {"plan": sealed / identity.PLAN_PATH, "ready": sealed / identity.READY_PATH,
            "reservation": _reservation(sealed)}[role]
    original = path.read_bytes()
    if damage == "missing":
        path.unlink()
    elif damage == "bytes":
        path.write_bytes(b"{}")
    elif damage == "extra-key":
        data = json.loads(original)
        data["unregistered"] = None
        path.write_bytes(_json(data))
    elif damage == "noncanonical":
        path.write_bytes(original + b"\n")
    else:
        other = tmp_path / "other-file"
        other.write_bytes(original)
        path.unlink()
        path.symlink_to(other) if damage == "symlink" else os.link(other, path)
    before = _tree(sealed.parent)
    with pytest.raises(identity.PilotIdentityRefused):
        identity.verify_pilot_identity(plan, bundle_root=sealed)
    report = pilot.inspect_plan(plan, identity_bundle=sealed)
    assert report["identity_plan_gate"]["refusal_code"] == "pilot_identity_plan_gate_refused"
    assert report["identity_plan_gate"]["cleared_blockers"] == []
    assert report["launch_blockers"] == ALL_BLOCKERS
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert _tree(sealed.parent) == before


@pytest.mark.parametrize("keys,value", [
    (("dispatch", "task_ids"), TASK_IDS[::-1]), (("grading", "tasks"), []),
    (("grading", "inference_revision"), "a" * 40), (("grading", "judge", "reasoning_effort"), "low"),
    (("dispatch", "condition"), "sandbox_v2"), (("dispatch", "repeat"), 2),
    (("contract_sha256",), "a" * 64), (("grading", "template_source_hash"), "a" * 64),
    (("evidence_linkage",), {"ready_bundle_sha256": "a" * 64}), (("launch_allowed",), True),
])
def test_forged_matching_markers_cannot_bypass_recompilation(plan, sealed, keys, value):
    document = json.loads((sealed / identity.PLAN_PATH).read_bytes())
    _set(document, keys, value)
    forged = identity.PilotIdentityPlan(identity._canonical_json(document))
    (sealed / identity.PLAN_PATH).write_bytes(forged.canonical_bytes())
    (sealed / identity.READY_PATH).write_bytes(identity._ready(forged))
    _reservation(sealed).write_bytes(identity._reservation(forged))
    with pytest.raises(identity.PilotIdentityRefused):
        identity.verify_pilot_identity(plan, bundle_root=sealed)


@pytest.fixture(scope="module")
def source_seed():
    root = pilot.ROOT
    names = set(pilot.REQUIRED_SOURCES) | {pilot.ACTIVE_PLAN, "batch-runner/scripts/download_inference_from_hf.py"}
    names.update(path.relative_to(root).as_posix() for path in (root / "batch-runner/core").rglob("*.py"))
    names.update(path.relative_to(root).as_posix()
                 for path in step8._requirements_closure(root / "batch-runner", root / "batch-runner/requirements.txt"))
    return tuple((path.relative_to(root).as_posix(), path.read_bytes()) for path in sorted(root / name for name in names))


@pytest.mark.parametrize("role,damage", [
    (pilot.GRADER, "bytes"), (pilot.ACTIVE_PLAN, "bytes"),
    ("batch-runner/core/grade_payload.py", "missing"),
    ("batch-runner/core/grade_payload.py", "hardlink"),
    ("batch-runner/core/grade_payload.py", "symlink"),
    ("batch-runner/core/unregistered_identity_test.py", "extra"),
    ("batch-runner/requirements-renderer.txt", "bytes"),
    ("batch-runner/prompts/grader_judge_v2.md", "bytes"),
    ("batch-runner/schemas/grade.schema.json", "bytes"),
])
def test_current_source_closure_is_rechecked_not_just_the_declared_pins(plan, tmp_path, source_seed, monkeypatch, role, damage):
    root = tmp_path / "source"
    _copy(source_seed, root)
    monkeypatch.setattr(pilot, "ROOT", root)
    path = root / role
    if role == pilot.ACTIVE_PLAN:
        changed = yaml.safe_load(path.read_bytes())
        changed["pilot"]["run_id"] = "stale-run"
        path.write_bytes(_json(changed))
    elif damage == "missing":
        path.unlink()
    elif damage in ("hardlink", "symlink"):
        other = tmp_path / "source-copy"
        other.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(other) if damage == "symlink" else os.link(other, path)
    else:
        path.write_bytes(b"# drift\n" if damage == "extra" else path.read_bytes() + b"\n# drift\n")
    with pytest.raises(identity.PilotIdentityRefused):
        identity.compile_pilot_identity(plan)
    if damage == "symlink":
        assert path.is_symlink()
    elif damage == "hardlink":
        assert path.stat().st_nlink == 2
    else:
        assert _tree(root) != source_seed


@pytest.mark.parametrize("role", [pilot.ENVELOPE + "gdpval_task_catalog.json", "batch-runner/prompts/grader_judge_v2.md"])
def test_consumed_snapshot_is_pinned_even_if_the_file_is_restored(plan, tmp_path, source_seed, monkeypatch, role):
    root = tmp_path / "source"
    _copy(source_seed, root)
    monkeypatch.setattr(pilot, "ROOT", root)
    path = root / role
    original = path.read_bytes()
    real, reads = identity._read_bytes, []

    def transient(candidate, **expected):
        if candidate != path:
            return real(candidate, **expected)
        reads.append(candidate)
        # Change only the consumed snapshot, after active-plan validation.
        if role.endswith(".json"):
            changed = json.loads(original)
            next(task for task in changed["tasks"] if task["task_id"] == TASK_IDS[0])["prompt_sha256"] = "a" * 64
            data = _json(changed)
        else:
            data = original + b"\nAltered wording, same prompt version.\n"
        path.write_bytes(data)
        try:
            return real(candidate, **expected)
        finally:
            path.write_bytes(original)

    monkeypatch.setattr(identity, "_read_bytes", transient)
    with pytest.raises(identity.PilotIdentityRefused):
        identity.compile_pilot_identity(plan)
    assert reads and path.read_bytes() == original
    assert _tree(root) == source_seed


@pytest.mark.parametrize("stage", ["sha256", "as_dict"])
def test_late_report_failure_retains_identity_blocker_after_real_verification(plan, linked, monkeypatch, stage):
    root, options = linked
    real = identity.verify_pilot_identity
    calls = []

    def unreadable(*args, **kwargs):
        verified = real(*args, **kwargs)
        calls.append(verified)

        class BrokenReport:
            @property
            def sha256(self):
                if stage == "sha256":
                    raise ValueError(SENTINEL)
                return verified.sha256

            def as_dict(self):
                raise ValueError(SENTINEL)

        return BrokenReport()

    monkeypatch.setattr(identity, "verify_pilot_identity", unreadable)
    report = pilot.inspect_plan(plan, identity_bundle=root, **options)
    assert len(calls) == 1
    assert report["launch_blockers"] == report["evidence_gate"]["remaining_blockers"] == REMAINING
    assert report["identity_plan_gate"]["remaining_blockers"] == REMAINING
    assert report["identity_plan_gate"]["identity_complete"] is False
    assert SENTINEL not in _json(report).decode()


@pytest.mark.parametrize("damage", [
    "omitted", "wrong-sha", "abbreviated-sha", "stale", "early", "bad-time",
    "missing-ready", "artifact", "missing-reservation", "hardlink", "stale-plan", "stale-base", "wrong-run", "partial",
])
def test_linked_evidence_must_be_reverified_and_cannot_downgrade_to_null(plan, linked, damage, tmp_path):
    root, options = linked
    if damage == "omitted":
        options = {}
    elif damage in ("wrong-sha", "abbreviated-sha"):
        options["reviewed_source_sha"] = "d" * (40 if damage == "wrong-sha" else 7)
    elif damage in ("stale", "early", "bad-time"):
        options["as_of"] = {"stale": "2026-10-02T00:00:00Z", "early": "2026-09-20T02:30:00Z", "bad-time": SENTINEL}[damage]
    elif damage == "missing-ready":
        (options["evidence_bundle"] / evidence.READY_PATH).unlink()
    elif damage == "missing-reservation":
        options["evidence_bundle"].with_name("bundle.foundry-evidence-reservation.json").unlink()
    elif damage in ("stale-plan", "stale-base", "wrong-run", "partial"):
        path = options["evidence_bundle"] / evidence.INTAKE_PATH
        intake = json.loads(path.read_bytes())
        if damage == "partial":
            intake["claims"][0]["artifact"] = None
        else:
            key = {"stale-plan": "plan_sha256", "stale-base": "plan_base_sha", "wrong-run": "run_id"}[damage]
            intake[key] = "a" * (64 if damage == "stale-plan" else 40) if damage != "wrong-run" else "other-run"
        path.write_bytes(_json(intake))
    else:
        artifact = options["evidence_bundle"] / "artifacts/identity.json"
        if damage == "artifact":
            artifact.write_bytes(artifact.read_bytes() + b"\n")
        else:
            os.link(artifact, tmp_path / "linked-artifact")
    with pytest.raises(identity.PilotIdentityRefused):
        identity.verify_pilot_identity(plan, bundle_root=root, **options)
    report = pilot.inspect_plan(plan, identity_bundle=root, **options)
    assert report["identity_plan_gate"]["identity_complete"] is False
    assert report["launch_blockers"] == ALL_BLOCKERS
    assert SENTINEL not in _json(report).decode()


@pytest.mark.parametrize("case", ["target", "reservation", "symlink-parent", "traversal", "source-overlap", "extra-member"])
def test_destination_collision_escape_and_partial_reuse_are_refused(plan, sealed, tmp_path, case):
    target = tmp_path / "absent"
    if case == "target":
        target.mkdir()
    elif case == "reservation":
        _reservation(target).write_bytes(b"reserved")
    elif case == "symlink-parent":
        (tmp_path / "alias").symlink_to(tmp_path, target_is_directory=True)
        target = tmp_path / "alias/absent"
    elif case == "traversal":
        target = tmp_path / "identity/../absent"
    elif case == "source-overlap":
        target = pilot.ROOT / "absent-identity-test-no-write"
    else:
        (sealed / "extra").write_bytes(b"not registered")
        with pytest.raises(identity.PilotIdentityRefused):
            identity.verify_pilot_identity(plan, bundle_root=sealed)
        return
    with pytest.raises(identity.PilotIdentityRefused):
        identity.publish_pilot_identity(plan, destination=target)
    assert not (target / identity.READY_PATH).exists()


@pytest.mark.parametrize("failed_write", [1, 2, 3])
def test_failure_never_publishes_ready_and_retains_partial_state(plan, tmp_path, monkeypatch, failed_write):
    target = tmp_path / "partial"
    calls, real = [], identity._write_no_clobber

    def failing(path, data):
        calls.append(path)
        if len(calls) == failed_write:
            raise OSError(SENTINEL)
        return real(path, data)

    monkeypatch.setattr(identity, "_write_no_clobber", failing)
    with pytest.raises(identity.PilotIdentityRefused) as error:
        identity.publish_pilot_identity(plan, destination=target)
    assert SENTINEL not in str(error.value)
    assert not (target / identity.READY_PATH).exists()
    assert _reservation(target).exists() == (failed_write > 1)
    assert (target / identity.PLAN_PATH).exists() == (failed_write > 2)
    if failed_write > 1:
        before = _tree(tmp_path)
        monkeypatch.setattr(identity, "_write_no_clobber", real)
        with pytest.raises(identity.PilotIdentityRefused):
            identity.publish_pilot_identity(plan, destination=target)
        assert _tree(tmp_path) == before


@pytest.mark.parametrize("damage", ["installed-plan", "source"])
def test_mid_publication_drift_leaves_no_ready_marker(plan, tmp_path, source_seed, monkeypatch, damage):
    source = tmp_path / "source"
    _copy(source_seed, source)
    monkeypatch.setattr(pilot, "ROOT", source)
    target = tmp_path / "identity"
    real = identity._write_no_clobber

    def change_after_plan(path, data):
        real(path, data)
        if path.name == identity.PLAN_PATH:
            changed = path if damage == "installed-plan" else source / pilot.GRADER
            changed.write_bytes(changed.read_bytes() + b"\n")

    monkeypatch.setattr(identity, "_write_no_clobber", change_after_plan)
    with pytest.raises(identity.PilotIdentityRefused):
        identity.publish_pilot_identity(plan, destination=target)
    assert _reservation(target).is_file() and (target / identity.PLAN_PATH).is_file()
    assert not (target / identity.READY_PATH).exists()
    before = _tree(target)
    with pytest.raises(identity.PilotIdentityRefused):
        identity.publish_pilot_identity(plan, destination=target)
    assert _tree(target) == before


def test_held_parent_replacement_is_refused_before_ready(plan, tmp_path, monkeypatch):
    parent = tmp_path / "held"
    parent.mkdir()
    target = parent / "identity"
    real = identity._write_no_clobber

    def replace_parent(path, data):
        real(path, data)
        if path.name == identity.PLAN_PATH:
            parent.rename(tmp_path / "displaced")
            parent.mkdir()

    monkeypatch.setattr(identity, "_write_no_clobber", replace_parent)
    with pytest.raises(identity.PilotIdentityRefused):
        identity.publish_pilot_identity(plan, destination=target)
    displaced = tmp_path / "displaced"
    assert (displaced / "identity" / identity.PLAN_PATH).is_file()
    assert not (displaced / "identity" / identity.READY_PATH).exists()
    assert _tree(parent) == ()


@pytest.mark.parametrize("entry,args", [
    (identity.main, ["--unknown", SENTINEL]),
    (identity.main, ["--plan", SENTINEL]),
    (identity.main, ["--reviewed-source-sha", SENTINEL]),
    (identity.main, ["--destination", SENTINEL, "--verify-bundle", SENTINEL]),
    (pilot.main, ["--identity-bundle", SENTINEL]),
    (pilot.main, ["--identity-bundel", SENTINEL]),
])
def test_cli_refusals_never_echo_untrusted_values(entry, args, capsys):
    assert entry(args) == 2
    output = capsys.readouterr()
    assert not output.err and SENTINEL not in output.out
    report = json.loads(output.out)
    assert report["launch_allowed"] is report["full_220_allowed"] is False


def test_case_mutations_cannot_reach_another_copy_or_immutable_seed(sealed, tmp_path, identity_seeds):
    seed = identity_seeds()
    other = tmp_path / "other-copy"
    _copy(seed, other)
    (sealed / identity.PLAN_PATH).write_bytes(b"mutation")
    assert identity_seeds() == seed == _tree(other)
    assert (other / "identity" / identity.PLAN_PATH).stat().st_ino != (sealed / identity.PLAN_PATH).stat().st_ino
