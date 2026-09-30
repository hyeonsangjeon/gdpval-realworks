"""One OFFLINE fixed bridge: real validators, synthetic records and transports.

Production pins are checked separately before fixture-only expected identities
are bound to synthetic bytes. Git metadata, HF, rename, renderer and the owned
judge transport are simulated; no source approval or paid result is proved.
"""

from copy import deepcopy
from dataclasses import replace
import ctypes
import errno
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest
import yaml

import codex_retention_fixed_grade as bridge
import gpt54_disposable_checkout as checkout
import gpt54_v2_grading_input as materializer
from step2_run_inference import _build_execution_observability
from . import test_codex_budget_pilot_grading as base
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401
from .test_codex_budget_pilot_retention import offline, TOKEN  # noqa: F401
from .test_codex_retention_result_intake import ResultHF, TERMINAL_HEAD

grade, pilot, reader, retained, output = bridge.grade, bridge.pilot, bridge.reader, bridge.retained, bridge.output
SOURCE = "d" * 40  # Synthetic reviewed controller transport fact, not a live reviewed commit.
RUN = {"id": "12345", "job": "pilot-live", "attempt": 1}


def _environment(monkeypatch):
    env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": bridge.pilot_ci.REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": SOURCE, "PILOT_WORKFLOW_SHA": SOURCE, "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": bridge.pilot_ci.REPOSITORY + "/" + grade.WORKFLOW + "@refs/heads/main",
        "GITHUB_RUN_ID": RUN["id"], "GITHUB_JOB": RUN["job"], "PILOT_GRADE_PAID_APPROVAL": "true",
        "PILOT_GRADE_DRY_RUN": "false", "PILOT_GRADE_APPROVAL_RESULT": "success",
        "GRADE_SELECTOR": bridge.SELECTOR, "GRADE_TERMINAL": bridge.RESULT["terminal_commit"],
        "GRADE_CONFIG": "default_v2_sol_max.yaml", "GRADE_FORCE": "false", "GRADE_TASKS_LIMIT": "0",
        "GRADE_TASKS": "", "GRADE_RESUME": "false", "GRADE_RESUME_CHUNK": "0", "GRADE_SHARD_COUNT": "1",
        "GRADE_SHARD_INDEX": "0", "GRADE_RUN_ORDINAL": "1",
        "PILOT_GRADE_APPROVAL_REQUEST_SHA256": pilot._digest(bridge.approval_request(SOURCE, RUN))}
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def _workflow_contract(tmp_path, monkeypatch):
    workflow = yaml.safe_load((bridge.ROOT / grade.WORKFLOW).read_bytes())
    jobs = workflow["jobs"]
    for name in ("validate-request", "approve-paid", "grade-dry-run", "grade", "verify-published"):
        assert "!startsWith(inputs.experiment_yaml, 'pilot/')" in jobs[name]["if"]
        assert "!startsWith(inputs.experiment_yaml, 'retention/')" in jobs[name]["if"]
    plan, approval, live = (jobs[name] for name in ("pilot-plan", "pilot-approve-paid", "pilot-live"))
    assert "startsWith(inputs.experiment_yaml, 'retention/')" in plan["if"]
    assert "inputs.experiment_yaml != 'retention/first-cell'" in plan["if"]
    assert "secrets." not in yaml.safe_dump(plan) and plan["permissions"] == {"contents": "read"}
    for job in (approval, live):
        assert "|| inputs.experiment_yaml == 'retention/first-cell'" in job["if"]
        assert "inputs.dry_run == false" in job["if"] and "inputs.paid_approval == true" in job["if"]
    assert approval["permissions"] == {} and approval["environment"] == {"name": "grading"}
    assert len(approval["steps"]) == 1 and "secrets." not in yaml.safe_dump(approval)
    assert live["permissions"] == {"contents": "read", "id-token": "write"}
    assert live["needs"] == ["pilot-approve-paid"] and "environment" not in live
    assert live["timeout-minutes"] == 300 and live["container"] == jobs["grade"]["container"]
    assert live["container"]["image"].endswith("@sha256:0f6782c056e31e1ea1d693fc2f8f873da160b232926fa1b6cde75c24e5344a04")
    assert plan["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"] == live["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
    assert "inputs.experiment_yaml == 'retention/first-cell' && '" + reader.PRODUCER_SOURCE + "'" in live["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
    assert "HF_TOKEN" not in live["env"]
    steps = live["steps"]
    gate = next(i for i, step in enumerate(steps) if step.get("name") == "Validate the exact selected pilot route")
    token_phases = set()
    for index, step in enumerate(steps):
        text = step.get("run", "")
        assert "upload-artifact" not in step.get("uses", "")
        if "HF_TOKEN" in step.get("env", {}):
            assert index > gate
            args = text.split()
            token_phases.add(args[args.index("--phase") + 1])
        if "azure" in text.lower() or "azure/login" in step.get("uses", ""):
            assert index > gate and "steps.pilot_input.outputs.judge_ready == 'true'" in step["if"]
        if "--phase record-ungraded" in text:
            assert "retention/" not in step["if"]
    assert token_phases == {"setup", "inspect", "prepare", "claim", "publish", "record-ungraded"}
    judge = next(step for step in steps if step.get("id") == "pilot_judge")
    assert judge["timeout-minutes"] == 245 and "steps.pilot_claim.outcome == 'success'" in judge["if"]
    assert "HF_TOKEN" not in judge.get("env", {}) and grade.CHILD_SECONDS == 242 * 60

    script = approval["steps"][0]["run"].removeprefix("python3 - <<'PY'\n").removesuffix("PY\n")
    destination = tmp_path / "protected-approval-output"

    def digest(inputs):
        with monkeypatch.context() as scoped:
            scoped.setenv("PILOT_GRADE_INPUTS_JSON", json.dumps(inputs))
            scoped.setenv("GITHUB_OUTPUT", str(destination))
            scoped.setenv("GITHUB_JOB", "pilot-approve-paid")
            exec(compile(script, "<protected-fixed-grade-approval>", "exec"), {})
        return destination.read_text().splitlines()[-1].removeprefix("request_sha256=")

    assert digest(bridge._fixed_inputs()) == pilot._digest(bridge.approval_request(SOURCE, RUN))
    for key, value in (("force", True), ("resume", True), ("shard_count", 2), ("shard_index", 1),
                       ("tasks", "other"), ("run_ordinal", 2), ("inference_revision", "e" * 40),
                       ("grading_config", "other.yaml"), ("paid_approval", False)):
        before = destination.read_bytes()
        with pytest.raises(SystemExit, match="^fixed_retention_grade_inputs_refused$"):
            digest({**bridge._fixed_inputs(), key: value})
        assert destination.read_bytes() == before
    legacy = {**bridge._fixed_inputs(), "experiment_yaml": "pilot/" + grade.RETAINED_CELL,
              "inference_revision": grade.RETAINED_TERMINAL}
    assert digest(legacy) == grade._approval_request_sha256(SOURCE, legacy["experiment_yaml"],
        legacy["inference_revision"], RUN, producer_source_sha=grade.RETAINED_PRODUCER_SOURCE)


def _seed_parent(api, monkeypatch):
    """Synthetic identities for the exact seven-pair rule, never live evidence."""
    cells = (grade.TASK5_B2_CELL, grade.TASK5_C2_CELL, grade.TASK5_C1_CELL,
             grade.TASK5_B1_CELL, grade.TASK5_A1_CELL, grade.TASK4_A2_CELL,
             "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2")
    previous, link = retained.BOOTSTRAP, None
    history = []
    for index in reversed(range(7)):
        cell = cells[index]
        claim_revision, terminal_revision = f"{200 + index * 2:040x}", f"{201 + index * 2:040x}"
        claim_path, terminal_path = grade._paths({"cell_id": cell, "run_id": bridge.PARENT["campaign_id"] + "__" + cell})
        binding = {"synthetic_fixed_history_cell": cell}
        claim = {"format": grade.CLAIM_FORMAT if index in {0, 2, 6} else bridge.ungraded.CLAIM_FORMAT,
                 "binding": binding, "expected_parent": previous, "predecessor": link}
        raw = retained._encoded(claim)
        api.seed(claim_revision, previous, {claim_path: raw})
        terminal = {"format": grade.TERMINAL_FORMAT if index in {0, 2, 6} else bridge.ungraded.TERMINAL_FORMAT,
                    "binding": binding, "claim_commit": claim_revision, "claim_identity": pilot._identity(raw)}
        raw = retained._encoded(terminal)
        api.seed(terminal_revision, claim_revision, {terminal_path: raw})
        previous = terminal_revision
        link = {"cell_id": cell, "revision": previous, **pilot._identity(raw)}
        history.append((terminal_revision, terminal_path))
    parent = deepcopy(bridge.PARENT)
    binding = {"campaign_id": parent["campaign_id"], "branch": parent["branch"], "cell_id": parent["cell_id"],
        "controller_source_sha": parent["writer_source_sha"], "source_sha": grade.TASK3_A1_PRODUCER_SOURCE,
        "github_run": parent["writer_run"], "policy": bridge.ungraded.TASK5_A2_POLICY,
        "proof_boundary": grade.PROOF, "repository_name_sha256": retained.TARGET_SHA256}
    claim = {"format": bridge.ungraded.CLAIM_FORMAT, "binding": binding, "expected_parent": previous, "predecessor": link}
    raw = retained._encoded(claim)
    parent["claim_identity"] = pilot._identity(raw)
    claim_path, terminal_path = grade._paths({"cell_id": parent["cell_id"], "run_id": parent["campaign_id"] + "__" + parent["cell_id"]})
    api.seed(parent["claim_revision"], previous, {claim_path: raw})
    terminal = bridge.ungraded._terminal(binding, {"returned_commit": parent["claim_revision"],
        "claim_identity": parent["claim_identity"]}, {"terminal": {"completion": {"status": "failed"}},
        "manifest": {"missing": []}})
    raw = retained._encoded(terminal)
    parent["terminal_identity"] = pilot._identity(raw)
    api.seed(parent["revision"], parent["claim_revision"], {terminal_path: raw})
    api.branches[grade.BRANCH] = parent["revision"]
    monkeypatch.setattr(bridge, "PARENT", parent)
    return history


class OwnedJudge(base.Child):
    def checkout(self, destination, sha):
        super().checkout(destination, sha)
        for name in ("codex_retention_result_intake.py", "codex_retention_ci.py"):
            shutil.copyfile(bridge.ROOT / "batch-runner" / name, destination / "batch-runner" / name)


def test_first_retention_fixed_grade_is_bound_one_use_and_private(tmp_path, monkeypatch, capsys):
    # These are production expectations. Fixture-only identities below do not
    # change the registered configuration, reader/verifier or actual closure.
    assert bridge.RESULT["terminal_commit"] == "de50ff0aa6037c0ef6e3b713da519359abd1d08d"
    assert bridge.RESULT["result"]["sha256"] == "07f335a07ffc8d921a0cfa0c7ab6bbc3728d704adc7c31f7ac1d3594728e3f67"
    assert bridge.PARENT["revision"] == "b057ed17849c0ab31b0adfb8c28109d4d34a50f7"
    assert bridge.PARENT["terminal_identity"] == {"sha256": "1443d6f9271c25d8ed27ea7179292ea43c790d26b4a37b079f6620b8ca25cd84", "size": 4260}
    assert bridge.PARENT["claim_identity"] == {"sha256": "81f1f8aa632145055b79b7d4b9cdfba7248b8f95b7f9caf552062e6854621d86", "size": 2425}
    assert bridge.READER == reader.reader_identity()
    assert bridge.fixed_evidence_sha256() == "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d"
    _environment(monkeypatch)
    _workflow_contract(tmp_path, monkeypatch)

    def capture():
        text = capsys.readouterr()
        assert not text.err
        assert TOKEN not in text.out and str(tmp_path) not in text.out and retained._target() not in text.out
        return json.loads(text.out)

    args = ["--reviewed-source-sha", SOURCE, "--root", str(tmp_path / "inert")]
    with monkeypatch.context() as scoped:
        scoped.delenv("GITHUB_ACTIONS")
        scoped.setattr(sys, "argv", ["codex_retention_fixed_grade.py", *args])
        with pytest.raises(SystemExit) as stopped:
            runpy.run_path(str(bridge.ROOT / "batch-runner/codex_retention_fixed_grade.py"), run_name="__main__")
        assert stopped.value.code == 0 and capture()["outcome"] == "plan_only"
        for extra in (("--force",), ("--resume",), ("--shard-count", "2"), ("--phase", "setup"),
                      ("--phase", "record-ungraded"), ("--selector", "retention/first-cell/extra")):
            assert bridge.main(args + list(extra)) == 2
            assert capture()["outcome"] == "refused"
        for selector in ("retention/other", "retention/first-cell-extra"):
            assert grade.main(args + ["--selector", selector]) == 2
            assert capture()["reason"] == "fixed_retention_grade_selector_required"
    assert not (tmp_path / "inert").exists()

    original = bridge.compile_request(SOURCE)
    assert original.run.command[2] == bridge.SELECTOR and original.run.grader_config_path == bridge.GRADER_PATH
    config = json.loads(original.run.grader_config_json)
    assert config["rubric"]["revision"] == "11e7900cdcac61bc4daf59e65feb238acda98fbf"
    assert config["judge"]["model"] == "gpt-5.6-sol" and config["judge"]["reasoning"]["effort"] == "max"
    with pytest.raises(output.OutputPublicationRefused, match="^canonical_retention_grade_context_required$"):
        bridge._context(SimpleNamespace(**original.__dict__))
    real_origins = bridge._origins(original)
    assert real_origins[0] == config["rubric"]["revision"]

    monkeypatch.setenv("HF_TOKEN", TOKEN)
    synthetic = ResultHF(original.plan, with_ledger=True)
    dispatch_config = json.loads(original.grading.dispatch.runs[0].config_json)
    synthetic.payload.update(experiment_name=dispatch_config["experiment"]["name"],
        condition=dispatch_config["condition_a"]["name"], started_at="2026-09-30T00:00:00Z",
        completed_at="2026-09-30T00:01:00Z", resume_rounds_used=0,
        summary={"total": 1, "success": 1, "error": 0, "qa_failed": 0})
    synthetic.payload["results"][0].update(deliverable_text="synthetic answer", latency_ms=1.0,
        timestamp="2026-09-30T00:01:00Z", error=None,
        observability=_build_execution_observability({}, []))
    synthetic.bind_payload()
    synthetic.seed()
    record = reader.read_result(expectation=reader.EXPECTATION, destination=tmp_path / "synthetic-pin",
        expected_reader_sha256=bridge.READER["module_sha256"], terminal_revision=TERMINAL_HEAD,
        discover_terminal=False, _test_api=synthetic)
    expected = {key: deepcopy(record[key]) for key in bridge.RESULT}
    expected["result"] = {key: record["result"][key] for key in bridge.RESULT["result"]}
    monkeypatch.setattr(bridge, "RESULT", expected)
    api = base.GradeHF()
    api.trees.update(deepcopy(synthetic.trees))
    api.writers.update(deepcopy(synthetic.writers))
    api.parents.update(deepcopy(synthetic.parents))
    api.head = TERMINAL_HEAD
    api.main_snapshot = deepcopy(api.trees[TERMINAL_HEAD])
    history = _seed_parent(api, monkeypatch)
    context = bridge.compile_request(SOURCE)
    _environment(monkeypatch)
    root = tmp_path / "one-private-grade"
    case = SimpleNamespace(root=root, context=context, api=api)
    base._synthetic_rubric(case, monkeypatch)
    synthetic_origins = base.intake._hf_origins()
    monkeypatch.setattr(bridge, "_origins", lambda supplied: synthetic_origins if supplied is context else
                        pytest.fail("unexpected synthetic original-input scope"))

    def rename(src_fd, src, dest_fd, dest, flags):
        assert flags == 1
        if os.path.lexists(Path(f"/proc/self/fd/{dest_fd}") / os.fsdecode(dest)):
            ctypes.set_errno(errno.EEXIST)
            return -1
        os.rename(src, dest, src_dir_fd=src_fd, dst_dir_fd=dest_fd)
        return 0

    monkeypatch.setattr(materializer, "_no_replace_rename", lambda: rename)
    common = tmp_path / "synthetic-git-metadata"
    common.mkdir()
    git_state, git_calls = {"head": SOURCE}, []

    def git(path, *command, ok=(0,)):
        assert Path(path) == bridge.ROOT or Path(path) == root / "source"
        git_calls.append(command)
        answers = {("rev-parse", "--show-toplevel"): os.fsencode(path) + b"\n",
            ("rev-parse", "--path-format=absolute", "--git-common-dir"): os.fsencode(common) + b"\n",
            ("rev-parse", "HEAD"): (git_state["head"] + "\n").encode(),
            ("diff", "--name-only", "HEAD", "--"): b"",
            ("status", "--porcelain", "--untracked-files=normal"): b"",
            ("config", "--name-only", "--get-regexp",
             r"^(filter\.|include\.|includeif\.|extensions\.partialclone$|remote\..*\.promisor$|core\.alternaterefscommand$)"): b""}
        assert command in answers, "nonallowlisted metadata command"
        return SimpleNamespace(stdout=answers[command], returncode=0)

    monkeypatch.setattr(pilot, "_git", git)
    monkeypatch.setattr(checkout, "_git", git)
    transport = OwnedJudge(case)
    before = len(api.calls)
    for variable, value in (("PILOT_GRADE_APPROVAL_REQUEST_SHA256", "0" * 64),
            ("PILOT_GRADE_APPROVAL_RESULT", "skipped"), ("GITHUB_RUN_ATTEMPT", "2"),
            ("GRADE_FORCE", "true"), ("GRADE_RESUME", "true"), ("GRADE_SHARD_COUNT", "2")):
        with monkeypatch.context() as scoped:
            scoped.setenv(variable, value)
            with pytest.raises(output.OutputPublicationRefused):
                bridge.prepare(context, root, _test_api=api, _test_transport=transport)
        assert len(api.calls) == before and not root.exists() and transport.calls == 0
    git_state["head"] = "e" * 40
    with pytest.raises(output.OutputPublicationRefused, match="^retention_grade_source_changed$"):
        bridge.prepare(context, root, _test_api=api, _test_transport=transport)
    git_state["head"] = SOURCE
    assert len(api.calls) == before and not root.exists()

    prepared = bridge.prepare(context, root, _test_api=api, _test_transport=transport)
    assert prepared["judge_ready"] is True and prepared["entry"]["grader_source_hash"] == bridge.GRADER_SHA256
    assert prepared["materialization"]["task_status"] == "success" and transport.calls == 0
    assert bridge._ready(context, root) == prepared
    assert not any(name == "commit" for name, _ in api.calls)
    for key, bad in (("producer_source_sha", "0" * 40), ("request_sha256", "0" * 64),
                     ("cell_id", "other"), ("terminal_commit", "0" * 40),
                     ("result", {**record["result"], "sha256": "0" * 64})):
        with pytest.raises(output.OutputPublicationRefused, match="^fixed_retention_result_mismatch$"):
            bridge._intake({**record, key: bad}, root / "retained")
    for changed in (replace(context, controller_source_sha="e" * 40),
                    replace(context, grading=replace(context.grading, runs=(replace(context.run,
                        grader_config_json=context.run.grader_config_json.replace('"max"', '"high"')),)))):
        with pytest.raises(output.OutputPublicationRefused):
            bridge._authority(changed)

    preparation_path = root / "prepared.json"
    original_preparation = preparation_path.read_bytes()
    for key, bad in (("entry", {**prepared["entry"], "grader_source_hash": "0" * 64}),
                     ("identity_sha256", "0" * 64), ("immutable_files", {})):
        preparation_path.write_bytes(retained._encoded({**prepared, key: bad}))
        with pytest.raises(output.OutputPublicationRefused):
            bridge._ready(context, root)
        preparation_path.write_bytes(original_preparation)
    assert transport.calls == 0

    # A fixed-parent drift or corrupted member must refuse before any CAS.
    api.branches[grade.BRANCH] = retained.BOOTSTRAP
    before_events = list(api.events)
    drift = bridge.claim(context, root, _test_api=api)
    assert drift["outcome"] == "unresolved" and drift["reason"] == "fixed_grading_parent_drift"
    assert api.events == before_events and not (root / "claim-reserved.json").exists()
    # This completed refusal is not retried: the following independent local
    # fixture has no receipt/reservation and models the unattempted success path.
    refused_root = root
    root = tmp_path / "independent-unattempted-grade"
    shutil.copytree(refused_root, root, ignore=shutil.ignore_patterns("claim-receipt.json", "parent"))
    case.root = root
    api.branches[grade.BRANCH] = bridge.PARENT["revision"]
    revision, member = history[0]
    saved = api.trees[revision][member]
    api.trees[revision][member] = b"{}\n"
    corrupt_cache = tmp_path / "corrupt-history"
    corrupt_cache.mkdir(mode=0o700)
    with retained._session(api) as (scoped_api, token, deadline):
        with pytest.raises(output.OutputPublicationRefused):
            bridge._parent(scoped_api, api.repo, corrupt_cache, token, deadline)
    api.trees[revision][member] = saved
    assert api.events == before_events

    admitted = bridge.claim(context, root, _test_api=api)
    assert admitted["outcome"] == "acknowledged" and api.events == ["grade_claim"]
    assert bridge._admission(context, root, prepared) == admitted
    with pytest.raises(output.OutputPublicationRefused, match="^retention_grade_claim_already_reserved$"):
        bridge.claim(context, root, _test_api=api)
    assert api.events == ["grade_claim"] and transport.calls == 0
    child = bridge.judge(context, root, _test_transport=transport)
    assert child == {"entry_invoked": True, "exit_code": 0, "timed_out": False, "cleanup_confirmed": True}
    assert transport.calls == 1 and api.events == ["grade_claim", "judge"]
    with pytest.raises((output.OutputPublicationRefused, FileExistsError)):
        bridge.judge(context, root, _test_transport=transport)
    assert transport.calls == 1

    child_path = root / "judge-receipt.json"
    child_path.write_bytes(retained._encoded({**child, "cleanup_confirmed": False}))
    with pytest.raises(output.OutputPublicationRefused, match="^grade_cleanup_unconfirmed$"):
        bridge.publish(context, root, _test_api=api)
    assert not (root / "publication-reserved.json").exists() and api.events == ["grade_claim", "judge"]
    child_path.write_bytes(retained._encoded(child))
    grade_path = root / "source" / prepared["entry"]["grade_path"]
    grade_bytes = grade_path.read_bytes()
    bad_grade = json.loads(grade_bytes)
    bad_grade["grader_source_hash"] = "0" * 64
    grade_path.write_bytes(retained._encoded(bad_grade))
    with pytest.raises(ValueError):
        bridge.publish(context, root, _test_api=api)
    assert not (root / "publication-reserved.json").exists()
    grade_path.write_bytes(grade_bytes)
    api.lost = "grade_output"
    publication = bridge.publish(context, root, _test_api=api)
    assert publication["outcome"] == "unresolved" and publication["reason"] == "hf_transport_failed"
    assert api.events == ["grade_claim", "judge", "grade_output"]
    assert bridge.reconcile(context, root, _test_api=api)["outcome"] == "verified_server_state"
    assert retained._read(root / "publication-receipt.json") == publication
    with pytest.raises((output.OutputPublicationRefused, FileExistsError)):
        bridge.publish(context, root, _test_api=api)
    assert transport.calls == 1 and api.events == ["grade_claim", "judge", "grade_output"]
    api.assert_main_unchanged()
    assert all(ref == grade.BRANCH for name, ref in api.calls if name == "commit")
    written = set(api.trees[api.branches[grade.BRANCH]]) - set(api.trees[bridge.PARENT["revision"]])
    assert written and all(name.startswith(bridge.PREFIX + "/") for name in written)
    assert all(not any(private in name for private in ("sqlite", "transcript", "judge.stdout", "judge.stderr")) for name in written)
    with pytest.raises(AssertionError):
        subprocess.run(["python", "-c", "pass"])
    assert git_calls and not capsys.readouterr().out
