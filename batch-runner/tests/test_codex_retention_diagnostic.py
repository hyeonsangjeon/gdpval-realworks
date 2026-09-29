"""One offline contract selector; no new inference, grade or private payload."""

from copy import deepcopy
import hashlib
import json

import pytest

import codex_budget_pilot as legacy
import codex_retention_diagnostic as diagnostic
from core.agentic_v2_preregistration import seal
from core.codex_task_deadline import CodexTaskDeadlineControl
from core.experiment_config import ExperimentConfig
from gpt54_comparison_preflight import _canonical_json, load_plan
from gpt54_prepared_input_attestation import PreparedInputRefused
from .test_codex_budget_pilot import offline  # noqa: F401; genuine process/network/client guards


def test_retention_registration_is_exact_closed_and_inert(
    tmp_path, monkeypatch, capsys, historical_budget_source,
):
    # The shared immutable legacy source is installed before the function guard.
    # The new compiler retains its own actual worktree ROOT and new source pins.
    registration = load_plan(diagnostic.ROOT / diagnostic.REGISTRATION)
    plan = diagnostic.compile_plan(registration)
    assert _canonical_json(plan) == _canonical_json(diagnostic.compile_plan())
    assert diagnostic.validate_plan(deepcopy(plan)) == plan
    expected = [
        ("3baa0009-5a60-4ae8-ae99-4955cb328ff3", "keep", 1),
        ("3baa0009-5a60-4ae8-ae99-4955cb328ff3", "fresh", 1),
        ("3baa0009-5a60-4ae8-ae99-4955cb328ff3", "fresh", 2),
        ("3baa0009-5a60-4ae8-ae99-4955cb328ff3", "keep", 2),
        ("0818571f-5ff7-4d39-9d2c-ced5ae44299e", "fresh", 1),
        ("0818571f-5ff7-4d39-9d2c-ced5ae44299e", "keep", 1),
        ("0818571f-5ff7-4d39-9d2c-ced5ae44299e", "keep", 2),
        ("0818571f-5ff7-4d39-9d2c-ced5ae44299e", "fresh", 2),
    ]
    expected_ids = [f"{task}_retention_bundle_v1_{bundle}_r{repeat}"
                    for task, bundle, repeat in expected]
    assert len(set(plan["order"])) == len(plan["cells"]) == plan["cell_count"] == 8
    assert len({cell["config"]["experiment"]["id"] for cell in plan["cells"]}) == 8
    assert plan["order"] == expected_ids
    assert plan["runtime_baseline"] == {
        "source_sha": "18bc942b97114cca3b9f6ed913b9841dda3a5874",
        "tree_sha": "062d668f967bb9e772f0de353dbef27e99987479",
        "reviewed_head": "610d39c2744be8b8879f884fa0a43abb053ecd44", "review_id": 5345799305,
    }
    assert plan["compiler_reviewed"] is plan["launch_authorized"] is False
    assert plan["scheduler_implemented"] is False and plan["commands"] == []
    assert plan["launch_blockers"] == list(diagnostic.LAUNCH_BLOCKERS)
    common = plan["common"]
    assert common["global_inference_slots"] == 1
    assert common["cumulative_seconds"] == 10800
    assert common["native_turn_wait_seconds"] == 1800
    assert common["native_turn_wait_is_all_in_attempt_ceiling"] is False
    assert common["max_admissions"] is None
    assert common["restart_outer_clock"] is common["c_recovery_context"] is False
    assert common["mechanical_recovery_policy"] == "B"
    assert common["recovery_failure_categories"] == ["rate_limited", "turn_start_failed"]
    assert common["backoff"] == "existing_B_including_index_restart_on_process_reentry"
    assert common["sdk"] == common["cli"] == "0.147.0"
    assert common["model"]["deployment"] == common["model"]["resolved_model"] == "gpt-5.4"
    assert common["model"]["reasoning_effort"] == "xhigh"
    assert common["shared_temporary_carveouts"] == "unchanged"

    normalized = []
    for index, (cell, (task, bundle, repeat)) in enumerate(zip(plan["cells"], expected)):
        assert cell["index"] == index and cell["cell_id"] == expected_ids[index]
        assert cell["task_id"] == task
        assert cell["control"] == {
            "condition": "retention_bundle_v1", "retention_bundle": bundle, "repetition": repeat,
        }
        config = cell["config"]
        assert ExperimentConfig.from_dict(config).validate() == []
        # The old assembly repeated the policy label and exceeded the real
        # identifier limit. The real validator must still refuse that ID shape.
        overlong = deepcopy(config)
        overlong["experiment"]["id"] = f"{diagnostic.CAMPAIGN}__{cell['cell_id']}"
        assert len(overlong["experiment"]["id"]) in {102, 103}
        assert ExperimentConfig.from_dict(overlong).validate() == [
            "experiment.id must be a safe identifier",
        ]
        assert len(config["experiment"]["id"]) <= 100
        assert config["data"]["filter"]["task_ids"] == [task]
        assert config["execution"]["max_retries"] == 3
        assert config["execution"]["timeout"] == 1800
        assert config["execution"]["codex"]["task_deadline"] == cell["control"]
        assert CodexTaskDeadlineControl.from_mapping(cell["control"]).as_dict() == cell["control"]
        assert cell["config_sha256"] == seal(config)
        assert config["condition_a"]["qa"]["enabled"] is False
        assert config["output"] == {"publish_to_hf": False, "submit_to_evals": False}
        same = deepcopy(config)
        assert same["experiment"].pop("id") == f"{diagnostic.CAMPAIGN}__{task}_{bundle}_r{repeat}"
        same["data"]["filter"].pop("task_ids")
        same["execution"]["codex"]["task_deadline"].pop("repetition")
        same["execution"]["codex"]["task_deadline"].pop("retention_bundle")
        normalized.append(same)
    assert all(config == normalized[0] for config in normalized)

    inputs = plan["inputs"]
    assert inputs["revision"] == "11e7900cdcac61bc4daf59e65feb238acda98fbf"
    assert inputs["parquet_sha256"] == "f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202"
    assert inputs["tasks"][0]["prompt_sha256"] == "cd6b2d63e8d90a7058bd7d4d9ff3a94e258268b54f78ec1ff3eff467437dbf76"
    assert inputs["tasks"][0]["reference_files"] == {}
    assert inputs["tasks"][1]["prompt_sha256"] == "718353295dc2778e76283739c455c4faf2c3ee18fb7e125495fd1e95e69aa6d5"
    reference = "reference_files/901e943a97328a661f9e704ae43eeea1/Acquisition Criteria (2).pdf"
    assert inputs["tasks"][1]["reference_files"] == {
        reference: "901e943a97328a661f9e704ae43eeea167e7805385a99322f1c24f8e159125c4",
    }
    assert inputs["verification_here"] == "public_provenance_only_no_private_payload_read"
    grading = plan["grading"]
    assert grading["judge_model"] == "gpt-5.6-sol" and grading["judge_effort"] == "max"
    assert grading["grades_per_produced_result"] == 1 and grading["no_result_grade"] is None
    assert grading["generated_config"]["rubric"]["revision"] == inputs["revision"]
    assert grading["generated_config_sha256"] == seal(grading["generated_config"])
    assert grading["template_source_sha256"] == "37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce"
    assert grading["materialized_grader_source_sha256"] is None
    assert plan["analysis"]["denominator"] == 8
    assert plan["analysis"]["no_recovery_opportunity"] == "uninformative_about_retention_remains_in_denominator"

    # Exact registered controls, not user-adjustable budget or launch knobs.
    edits = [
        (("campaign_id",), "unregistered"), (("launch_authorized",), True),
        (("compiler_reviewed",), True), (("cell_count",), 9),
        (("runtime_condition",), "B"), (("cells", 0, "retention_bundle"), "other"),
        (("cells", 0, "repetition"), True), (("cells", 0, "repetition"), 3),
        (("cells", 0, "task_id"), "0112fc9b-c3b2-4084-8993-5a4abb1f54f1"),
        (("common", "global_inference_slots"), 2), (("common", "max_admissions"), 4),
        (("common", "cumulative_seconds"), 10801), (("common", "native_turn_wait_seconds"), 10800),
        (("common", "native_turn_wait_is_all_in_attempt_ceiling"), True),
        (("common", "restart_outer_clock"), True), (("common", "c_recovery_context"), True),
        (("common", "model", "deployment"), "gpt-5.6-sol"),
        (("inputs", "revision"), "main"),
        (("inputs", "tasks", 0, "prompt_sha256"), "0" * 64),
        (("inputs", "tasks", 1, "reference_files", reference), "0" * 64),
        (("grading", "grades_per_produced_result"), 2), (("grading", "no_result_grade"), 0),
        (("analysis", "denominator"), 7), (("analysis", "automatic_expansion"), True),
        (("unexpected",), "unregistered_field"),
    ]
    for path, value in edits:
        changed = deepcopy(registration)
        parent = changed
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = value
        with pytest.raises(diagnostic.RetentionRegistrationRefused, match="^registration_mismatch$"):
            diagnostic.compile_plan(changed)
    for rows in (registration["cells"][:-1], list(reversed(registration["cells"])),
                 [registration["cells"][0]] * 8):
        with pytest.raises(diagnostic.RetentionRegistrationRefused, match="^registration_mismatch$"):
            diagnostic.compile_plan({**registration, "cells": rows})
    changed = deepcopy(registration)
    changed["grader_template_source_sha256"] = "0" * 64
    with pytest.raises(diagnostic.RetentionRegistrationRefused, match="^grader_template_source_mismatch$"):
        diagnostic.compile_plan(changed)

    # Genuine changed source bytes in a test-owned copy, including a refused
    # attempt to repin them while still claiming the reviewed runtime base.
    shadow = tmp_path / "changed-source"
    for paths in diagnostic.SOURCE_ROLES.values():
        for name in paths:
            target = shadow / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((diagnostic.ROOT / name).read_bytes())
    runtime = "batch-runner/core/codex_runner.py"
    (shadow / runtime).write_bytes(b"changed test-owned runtime bytes\n")
    with monkeypatch.context() as altered:
        altered.setattr(diagnostic, "ROOT", shadow)
        with pytest.raises(diagnostic.RetentionRegistrationRefused,
                           match="^source_pin:batch-runner/core/codex_runner.py$"):
            diagnostic.compile_plan(registration)
        repinned = deepcopy(registration)
        repinned["source_pins"]["runtime"][runtime] = hashlib.sha256((shadow / runtime).read_bytes()).hexdigest()
        with pytest.raises(diagnostic.RetentionRegistrationRefused, match="^baseline_source_pins_mismatch$"):
            diagnostic.compile_plan(repinned)
    changed = deepcopy(registration)
    changed["source_pins"]["compiler"][diagnostic.COMPILER] = "0" * 64
    with pytest.raises(diagnostic.RetentionRegistrationRefused,
                       match="^source_pin:batch-runner/codex_retention_diagnostic.py$"):
        diagnostic.compile_plan(changed)
    for field, value in (("launch_authorized", True), ("order", list(reversed(plan["order"]))),
                         ("cell_count", 9), ("commands", [["step2_run_inference.py"]])):
        with pytest.raises(diagnostic.RetentionRegistrationRefused, match="^compiled_plan_mismatch$"):
            diagnostic.validate_plan({**plan, field: value})

    # Real legacy compilation still yields only the frozen original 30 cells.
    old, _, _ = legacy.compile_pilot("offline-legacy-refusal", "8ac891e3e0e4752fe15a00139a2691ddf9df7dce")
    assert len(old["cells"]) == 30 and {cell["condition"] for cell in old["cells"]} == {"A", "B", "C"}
    assert set(expected_ids).isdisjoint(old["order"])
    old_registration = load_plan(legacy.REGISTRATION)
    old_registration["order_per_task"][0] = plan["cells"][0]["control"]
    invalid_legacy = tmp_path / "new-control-in-old-registration.json"
    invalid_legacy.write_text(_canonical_json(old_registration))
    with monkeypatch.context() as supplied:
        supplied.setattr(legacy, "REGISTRATION", invalid_legacy)
        with pytest.raises(PreparedInputRefused, match="^pilot registration mismatch$"):
            legacy.compile_pilot("offline-legacy-refusal", "8ac891e3e0e4752fe15a00139a2691ddf9df7dce")

    assert diagnostic.main([]) == 0
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["configuration_valid"] is True and emitted["launch_authorized"] is False
    assert emitted["plan"] == plan and emitted["plan_sha256"] == seal(plan)
    with pytest.raises(SystemExit) as launch:
        diagnostic.main(["--execute"])
    assert launch.value.code == 2
    assert "unrecognized arguments: --execute" in capsys.readouterr().err
