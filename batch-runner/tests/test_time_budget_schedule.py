"""Synthetic, model-free schedule/CAS/source proofs; no private result intake."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import time

import pytest
import yaml

import gpt54_time_budget_comparison as registration
import gpt54_time_budget_schedule as schedule
import gpt54_time_budget_v2_ci as v2
import gpt54_time_budget_codex_ci as codex
from core.agentic_v2_preregistration import seal
from .test_time_budget_first_v2_ci import PrivateStore, TOKEN
from .test_gpt54_disposable_checkout import _FIXTURE_ENV

ROOT = Path(__file__).resolve().parents[2]
SOURCE = {"sha": "a" * 40, "tree": "b" * 40}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("offline schedule proof attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    for name in v2.TOKEN_KEYS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def plan():
    return registration.load_registration(ROOT / registration.REGISTRATION_PATH)


def _context(plan, cell):
    return {"plan": plan, "cell": cell, "request": {"source": SOURCE}}


def _check(store, context, cache):
    cache.mkdir()
    schedule.require_next_remote(context, store, TOKEN, time.monotonic() + 30,
                                 repository=v2.TARGET, parent=store.head, cache=cache)


def test_exact_twenty_job_block_order_and_stable_ids(plan):
    jobs = schedule.job_descriptors(plan)
    assert jobs["launch_allowed"] is jobs["execution_enabled"] is False
    assert jobs["max_observations"] == 20 and jobs["inference_concurrency"] == 1
    ordered = schedule.build_schedule(plan)
    assert len(ordered) == len({item.observation_id for item in ordered}) == 20
    assert [(item.condition, item.repeat, item.abba_position, item.task_id) for item in ordered] == [
        (condition, repeat, position, task)
        for position, (condition, _, repeat) in enumerate(registration.RUN_ORDER, 1)
        for task in schedule.TASK_IDS]
    for index, job in enumerate(jobs["jobs"]):
        assert job["sequence"] == index + 1
        assert job["requires_capture"] == (ordered[index - 1].observation_id if index else None)
        assert job["workflow"] == schedule.WORKFLOWS[job["cell"]["condition"]]
        assert job["job"] == "observation" and job["runner"] == "ubuntu-24.04"
        assert job["concurrency_group"] == schedule.CONCURRENCY_GROUP
    # A reordered mapping, compiler/source change or image does not mint new observations.
    copied = json.loads(json.dumps(plan, sort_keys=True))
    copied["source_pins"][registration.COMPILER] = "0" * 64
    assert schedule.build_schedule(copied) == ordered


@pytest.mark.parametrize("field,value", [
    ("max_generation_observations", 21), ("repeats_per_condition", 3),
    ("inference_concurrency", 2), ("external_retry_allowed", True),
    ("external_resume_allowed", True), ("external_replay_allowed", True),
    ("external_attempts_per_observation", 2),
])
def test_scheduler_cannot_expand_the_registered_scope(plan, field, value):
    plan["scope"][field] = value
    with pytest.raises(schedule.ScheduleRefused, match="schedule_contract_mismatch"):
        schedule.build_schedule(plan)


@pytest.mark.parametrize("index", range(20))
def test_both_controllers_select_exactly_one_registered_r1_r2_cell(plan, index):
    compiled = registration.CompiledTimeBudgetRegistration(
        seal(plan), "{}", "{}", tuple(registration.TimeBudgetRunSpec(
            row["run_id"], row["condition"], row["repeat"], schedule.TASK_IDS) for row in plan["runs"]), True)
    item = schedule.build_schedule(plan)[index]
    controller = v2 if item.condition == "sandbox_v2" else codex
    assert controller._selected_cell(compiled, item.cell) == item.cell
    for field, value in (("repeat", 3), ("repeat", True), ("task_id", "not-registered"),
                         ("condition", "other"), ("run_id", "other")):
        with pytest.raises(ValueError):
            controller._selected_cell(compiled, {**item.cell, field: value})


@pytest.mark.parametrize("case,reason", [
    ("out_of_order", "observation_out_of_order"), ("duplicate", "observation_already_captured"),
    ("pending", "observation_already_claimed"), ("uncertain", "previous_observation_uncertain"),
    ("gap", "observation_out_of_order"), ("duplicate_history", "schedule_history_invalid"),
    ("unregistered", "observation_not_registered"), ("twenty_done", "observation_limit_exceeded"),
    ("twenty_one", "observation_limit_exceeded"),
])
def test_next_refusal_cases(plan, case, reason):
    order = schedule.build_schedule(plan)
    ids = [item.observation_id for item in order]
    captured, claimed, request = ids[:1], ids[:1], ids[1]
    if case == "out_of_order":
        request = ids[2]
    elif case == "duplicate":
        request = ids[0]
    elif case == "pending":
        claimed = ids[:2]
    elif case == "uncertain":
        claimed, request = ids[:2], ids[2]
    elif case == "gap":
        captured, claimed = ids[1:2], ids[1:2]
        request = ids[2]
    elif case == "duplicate_history":
        captured, claimed = [ids[0], ids[0]], ids[:1]
    elif case == "unregistered":
        request = "0" * 64
    elif case == "twenty_done":
        captured, claimed, request = ids, ids, None
    elif case == "twenty_one":
        captured, claimed, request = ids + ["x"], ids + ["x"], None
    with pytest.raises(schedule.ScheduleRefused, match="^" + reason + "$"):
        schedule.next_observation(order, captured_ids=captured, claimed_ids=claimed, requested_id=request)


def test_twenty_serial_jobs_use_real_shared_cas_and_continue_from_captures(plan, tmp_path):
    store = PrivateStore()
    order = schedule.build_schedule(plan)
    captures = []
    for item in order:
        assert schedule.next_observation(order, captured_ids=captures, claimed_ids=captures) == item
        context = _context(plan, item.cell)
        store.claim, store.manifest = item.prefix + "/admission.json", item.prefix + "/output-manifest.json"
        _check(store, context, tmp_path / f"admit-{item.sequence}")
        # Only the storage transport is synthetic. Both real controller CAS
        # implementations must publish each boundary and verify immutable bytes.
        controller = v2 if item.condition == "sandbox_v2" else codex
        claim = {"observation": item.cell, "fixture": "fake_transport_no_model"}
        cache = tmp_path / f"claim-{item.sequence}"
        cache.mkdir()
        claimed_at = controller._commit(store, TOKEN, time.monotonic() + 30,
            cell=item.cell, parent=store.head, files={store.claim: v2._encoded(claim),
                item.prefix + "/" + schedule.CLAIM_NAME: v2._encoded(schedule.claim_record(context, claim))},
            control_path=store.claim, control=claim, cache=cache)
        with pytest.raises(schedule.ScheduleRefused, match="observation_already_claimed"):
            _check(store, context, tmp_path / f"duplicate-claim-{item.sequence}")
        manifest = {"observation": item.cell, "execution_receipt": {"outcome": "returned"},
                    "fixture": "fake_capture_including_failed_outcomes"}
        # Failed terminal outcomes with confirmed cleanup also advance; scores
        # never select, drop or retry observations.
        payload = {"time_budget_observation": {"cleanup_complete": True, "host_reusable": True}}
        record = schedule.capture_record(context, {"claim": claim, "returned_commit": claimed_at}, manifest, payload)
        cache = tmp_path / f"capture-{item.sequence}"
        cache.mkdir()
        controller._commit(store, TOKEN, time.monotonic() + 30, cell=item.cell, parent=store.head,
            files={store.manifest: v2._encoded(manifest), item.prefix + "/" + schedule.CAPTURE_NAME: v2._encoded(record)},
            control_path=store.manifest, control=manifest, cache=cache)
        captures.append(item.observation_id)
        with pytest.raises(schedule.ScheduleRefused, match="observation_already_captured"):
            _check(store, context, tmp_path / f"duplicate-capture-{item.sequence}")
    assert store.commits == ["claim", "output"] * 20
    assert len(store.trees[store.head]) == 80
    with pytest.raises(schedule.ScheduleRefused, match="observation_limit_exceeded"):
        schedule.next_observation(order, captured_ids=captures, claimed_ids=captures)


def test_simultaneous_claims_have_one_cas_winner(plan, tmp_path):
    item = schedule.build_schedule(plan)[0]
    store, context = PrivateStore(), _context(plan, item.cell)
    parent = store.head
    _check(store, context, tmp_path / "reader-a")
    _check(store, context, tmp_path / "reader-b")
    claim = {"observation": item.cell, "fixture": "simultaneous_jobs"}
    for index in range(2):
        cache = tmp_path / f"writer-{index}"
        cache.mkdir()
        arguments = dict(cell=item.cell, parent=parent,
            files={store.claim: v2._encoded(claim), item.prefix + "/" + schedule.CLAIM_NAME:
                   v2._encoded(schedule.claim_record(context, claim))},
            control_path=store.claim, control=claim, cache=cache)
        if index == 0:
            v2._commit(store, TOKEN, time.monotonic() + 30, **arguments)
        else:
            with pytest.raises(v2.storage.OutputPublicationRefused):
                v2._commit(store, TOKEN, time.monotonic() + 30, **arguments)
    assert len(store.trees) == 2 and len(store.trees[store.head]) == 2


@pytest.mark.parametrize("case,reason", [
    ("no_prior", "observation_out_of_order"), ("future", "observation_out_of_order"),
    ("missing_capture", "previous_capture_unverified"), ("uncertain", "previous_observation_uncertain"),
    ("changed_id", "schedule_record_mismatch"), ("changed_source", "schedule_source_changed"),
    ("bool_position", "schedule_record_mismatch"),
    ("changed_manifest", "remote_output_blob_mismatch"),
])
def test_remote_schedule_stops_on_unverified_history(plan, tmp_path, case, reason):
    order = schedule.build_schedule(plan)
    context, store = _context(plan, order[1].cell), PrivateStore(prefix=order[1].prefix)
    if case != "no_prior":
        store.seed_captured_before(plan, order[1].cell, SOURCE)
    path = order[0].prefix + "/" + schedule.CAPTURE_NAME
    if case == "future":
        store.trees[store.head][order[2].prefix + "/admission.json"] = b"synthetic unexpected future claim"
    elif case == "missing_capture":
        del store.trees[store.head][path]
    elif case in {"uncertain", "changed_id", "changed_source", "bool_position"}:
        record = json.loads(store.trees[store.head][path])
        if case == "uncertain":
            record["state"] = "uncertain_stop"
        elif case == "changed_id":
            record["binding"]["observation_id"] = "0" * 64
        elif case == "bool_position":
            record["binding"]["abba_position"] = True
        else:
            record["source"]["sha"] = "0" * 40
        store.trees[store.head][path] = v2._encoded(record)
    elif case == "changed_manifest":
        manifest = order[0].prefix + "/output-manifest.json"
        data = store.trees[store.head][manifest]
        store.trees[store.head][manifest] = data.replace(b"capture", b"changed")
    before = deepcopy(store.trees)
    with pytest.raises(ValueError, match=reason):
        _check(store, context, tmp_path / "readback")
    assert store.trees == before and store.commits == []


def test_workflows_are_one_job_with_same_serial_group_and_no_loop(plan):
    for name in schedule.WORKFLOWS.values():
        flow = yaml.load((ROOT / name).read_text(), Loader=yaml.BaseLoader)
        assert set(flow["on"]) == {"workflow_dispatch"}
        assert flow["concurrency"] == {"group": schedule.CONCURRENCY_GROUP, "cancel-in-progress": "false"}
        assert set(flow["jobs"]) == {"observation"}
        job = flow["jobs"]["observation"]
        expected_minutes = "65" if "codex" in name else "55"
        assert job["runs-on"] == "ubuntu-24.04" and job["timeout-minutes"] == expected_minutes
        assert "strategy" not in job
        assert sum(" execute " in step.get("run", "") for step in job["steps"]) == 1
        guard = job["steps"][0]["run"]
        assert 'type(request["cell"]["repeat"]) is int' in guard and "repeat in (1, 2)" in guard


@pytest.fixture(scope="module")
def reviewed_sources(tmp_path_factory):
    """Full current working source anchored in a synthetic review commit."""
    parent = tmp_path_factory.mktemp("schedule-reviewed-source")
    owner, runtime, frozen = parent / "objects", parent / "runtime", parent / "frozen"
    environment = {**_FIXTURE_ENV, "GIT_ALLOW_PROTOCOL": "file"}

    def git(*args):
        return subprocess.run(["git", *args], env=environment, check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=60).stdout.decode().strip()

    git("clone", "--shared", "--", str(ROOT), str(owner))
    git("-C", str(owner), "worktree", "add", "--detach", str(runtime), "HEAD")
    git("-C", str(owner), "worktree", "add", "--detach", str(frozen), registration.ACCEPTED_BASE_SHA)
    for name in registration.FOLLOWUP_HELPERS | {registration.COMPILER, registration.SOURCE_FOLLOWUP_PATH}:
        shutil.copyfile(ROOT / name, runtime / name)
    git("-C", str(runtime), "add", "--", *sorted(registration.FOLLOWUP_HELPERS |
        {registration.COMPILER, registration.SOURCE_FOLLOWUP_PATH}))
    git("-C", str(runtime), "commit", "--allow-empty", "-m", "test: exact source-only schedule review fixture")
    return runtime, frozen, git("-C", str(runtime), "rev-parse", "HEAD")


def test_source_successor_compiles_without_changing_any_study_fact(plan, reviewed_sources):
    runtime, frozen, sha = reviewed_sources
    compiled = registration.compile_registration(plan, runtime_root=runtime, expected_reviewed_source_sha=sha,
        frozen_grader_root=frozen, expected_grader_source_sha=registration.ACCEPTED_BASE_SHA)
    value = compiled.as_dict()
    assert value["launch_authority"]["launch_allowed"] is False
    assert compiled.manifest_sha256 == seal(plan)
    evidence = value["source_evidence"]
    assert len(evidence["validated_source_pins"]) == 42
    assert evidence["frozen_grader"]["template_source_sha256"] == registration.FROZEN_TEMPLATE_SHA256
    followup = evidence["runtime"]["source_followup"]
    assert followup["predecessor"]["sha256"] == registration.PREDECESSOR_REGISTRATION_SHA256
    assert followup["sha256"] == hashlib.sha256((ROOT / registration.SOURCE_FOLLOWUP_PATH).read_bytes()).hexdigest()
    assert {row["path"] for row in followup["changed_files"]} == registration.FOLLOWUP_CHANGED_SOURCES
    assert evidence["validated_source_pins"]["batch-runner/core/codex_runner.py"] == (
        "b5f29c5aef7fc594ed3f042085a078e9e13c3f3754f5840c1df19bae75235c34")
    intent = value["registered_intent"]
    assert intent["shared"] == plan["shared"] and intent["generation_budget"] == plan["generation_budget"]
    assert intent["conditions"] == plan["conditions"] and intent["grading_policy"] == plan["grading_policy"]


@pytest.mark.parametrize("case", ["previous_hash", "missing_delta", "extra_delta", "new_hash", "helper_hash",
                                    "missing_helper", "extra_field", "changed_policy", "unlisted_source"])
def test_successor_cannot_waive_source_or_condition_guards(plan, tmp_path, case):
    root = tmp_path / "source"
    names = set(plan["source_pins"]) | registration.FOLLOWUP_HELPERS | {
        registration.REGISTRATION_PATH, registration.SOURCE_FOLLOWUP_PATH}
    for name in names:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, root / name)
    path = root / registration.SOURCE_FOLLOWUP_PATH
    record = registration.load_registration(path)
    if case == "previous_hash":
        record["changed_files"][0]["previous_sha256"] = "0" * 64
    elif case == "missing_delta":
        record["changed_files"].pop()
    elif case == "extra_delta":
        record["changed_files"].append(record["changed_files"][0])
    elif case == "new_hash":
        record["changed_files"][0]["sha256"] = "0" * 64
    elif case == "helper_hash":
        record["helper_pins"][schedule.HELPER] = "0" * 64
    elif case == "missing_helper":
        record["helper_pins"].pop(schedule.HELPER)
    elif case == "extra_field":
        record["waive_hash_checks"] = True
    elif case == "changed_policy":
        plan["generation_budget"]["seconds_per_observation"] = 999
    else:
        (root / "batch-runner/core/config.py").write_bytes(b"synthetic unlisted drift")
    path.write_text(yaml.safe_dump(record))
    with pytest.raises(ValueError):
        registration._runtime_source_followup(root, plan)


def test_successor_bytes_still_require_the_independent_git_anchor(plan, reviewed_sources):
    runtime, frozen, sha = reviewed_sources
    args = dict(runtime_root=runtime, expected_reviewed_source_sha=sha,
                frozen_grader_root=frozen, expected_grader_source_sha=registration.ACCEPTED_BASE_SHA)
    path = runtime / registration.SOURCE_FOLLOWUP_PATH
    raw = path.read_bytes()
    try:
        path.write_bytes(raw + b"\n# synthetic unreviewed successor change\n")
        with pytest.raises(registration.TimeBudgetRegistrationRefused, match="source_differs_from_reviewed_blob"):
            registration.compile_registration(plan, **args)
    finally:
        path.write_bytes(raw)
