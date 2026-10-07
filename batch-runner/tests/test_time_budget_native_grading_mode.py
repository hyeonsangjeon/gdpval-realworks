"""Native capture/preparation compatibility, not a native run or a grade."""

import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

import gpt54_time_budget_codex_observation as native
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_grading_preparation as preparation
from core.agentic_v2_preregistration import seal
from core.reference_integrity import ReferenceIntegrityError
from core.result_fingerprint import validate_inference_result_fingerprint
from gpt54_comparison_preflight import GRADER, _canonical_json, load_plan
from gpt54_prepared_input_attestation import _identity
from gpt54_v2_grading_input import V2GradingInputRefused
from .test_time_budget_grading_preparation import (
    _case, _store_result, _unpublished, dual_roots, handoff_source_seed,
    handoff_sources, offline,
)


@pytest.mark.parametrize("case", [
    "native_success", "native_error", "native_legacy_mode", "native_source",
    "native_observation", "native_bytes", "native_fingerprint",
    "v2_success", "v2_native_mode",
])
def test_time_budget_native_capture_grading_preparation(handoff_sources, tmp_path, offline, case):
    seed = handoff_sources
    condition = "sandbox_v2" if case.startswith("v2_") else "codex"
    status = "error" if case == "native_error" else "success"
    arguments, payload, prepared = _case(seed, tmp_path, condition=condition, status=status)
    original_inputs = {path: path.read_bytes() for path in (
        seed.parquet, *((seed.step0,) if condition == "codex" else ()),
        *(seed.references / role for role in seed.records))}
    frozen_roles = (GRADER, "batch-runner/step8_grade.py", "batch-runner/core/grader.py")
    frozen_bytes = {role: (seed.frozen / role).read_bytes() for role in frozen_roles}
    handoff = tmp_path / "publications/one-observation"
    preparation_bytes = (handoff / registration.HANDOFF_READY).read_bytes()
    assert json.loads(preparation_bytes) == prepared
    prepared_identity = _identity(preparation_bytes)

    if condition == "codex":
        # Only the returned runner data and direction metadata are synthetic.
        # No direction/admission success is substituted: neither is invoked.
        # The existing offline fixture refuses native/provider/grader effects.
        binding = registration.ObservationExecutionBinding(
            prepared_identity["sha256"], prepared_identity["size"],
            _canonical_json(prepared["observation"]), seed.frozen_sha,
            seed.frozen_tree, registration.FROZEN_TEMPLATE_SHA256,
            str(handoff), str(tmp_path / "unused-observation-store"),
        )
        direction = SimpleNamespace(
            binding=binding, expected=seal({"synthetic": "capture-only direction metadata"}),
            paths={"preparation": str(handoff), "result": str(arguments["result_path"])},
            host={"ownership_confirmed": False},
        )
        control = {**payload["time_budget_observation"], "generation_elapsed_seconds": 0.125}
        raw = {
            "success": status == "success",
            "error": None if status == "success" else "synthetic_native_failure",
            "text": "Synthetic native return data; no model." if status == "success" else "",
            "files": [{"filename": Path(item["path"]).name,
                       "content": (arguments["deliverables_root"] / item["path"]).read_bytes()}
                      for item in payload["results"][0]["deliverable_file_records"]],
            "time_budget_observation": control,
            "handoff_preparation_identity": prepared_identity,
        }
        payload, files = native._capture(raw, prepared, direction, provider_binding={})
        assert payload["condition"] == "codex" and payload["execution_mode"] == "codex_foundry"
        assert payload["time_budget_observation"] == control
        assert payload["observation_execution"]["runtime_source"] == prepared["runtime_source"]
        assert payload["observation_execution"]["frozen_grader"] == prepared["frozen_grader"]
        assert payload["observation_execution"]["inputs"] == prepared["inputs"]
        row = payload["results"][0]
        assert row["status"] == status and row["usage"] is None
        assert all(value is None for value in row["observability"]["native_measurements"].values())
        if status == "error":
            assert row["error"] == "time_budget_observation_non_success"
            assert row["deliverable_files"] == row["deliverable_file_records"] == []
            assert row["observability"]["usage_availability"]["usage_complete"] is False
            assert control["cleanup_complete"] is control["host_reusable"] is False
        assert files == {item["path"]: (arguments["deliverables_root"] / item["path"]).read_bytes()
                         for item in row["deliverable_file_records"]}
        # Preserve the producer's header and fingerprint exactly for valid cases.
        assert validate_inference_result_fingerprint(payload) == payload["result_fingerprint"]
        data = _canonical_json(payload).encode()
        arguments["result_path"].write_bytes(data)
        arguments["expected_result_identity"] = _identity(data)
    else:
        assert payload["condition"] == "sandbox_v2"
        assert payload["execution_mode"] == "agentic_sandbox_v2"

    semantic_errors = {
        "native_legacy_mode": "result execution_mode mismatch",
        "native_source": "result source mismatch",
        "native_observation": "result observation mismatch",
        "v2_native_mode": "result execution_mode mismatch",
    }
    if case in {"native_legacy_mode", "v2_native_mode"}:
        payload["execution_mode"] = "codex" if condition == "codex" else "codex_foundry"
    elif case == "native_source":
        payload["source"] = "synthetic/unregistered-dataset"
    elif case == "native_observation":
        payload["time_budget_observation"]["identity"]["reviewed_source_sha"] = "0" * 40
    if case in semantic_errors:
        _store_result(arguments, payload)  # Coherent hashes must not bypass semantic checks.
        assert validate_inference_result_fingerprint(payload) == payload["result_fingerprint"]
        assert arguments["expected_result_identity"] == _identity(arguments["result_path"].read_bytes())
    elif case == "native_bytes":
        arguments["expected_result_identity"] = {**arguments["expected_result_identity"], "sha256": "0" * 64}
    elif case == "native_fingerprint":
        payload["result_fingerprint"] = "0" * 64
        data = _canonical_json(payload).encode()
        arguments["result_path"].write_bytes(data)
        arguments["expected_result_identity"] = _identity(data)

    original_result = arguments["result_path"].read_bytes()
    original_deliverables = {path: path.read_bytes()
                            for path in arguments["deliverables_root"].rglob("*") if path.is_file()}
    if case in semantic_errors or case in {"native_bytes", "native_fingerprint"}:
        expected_type = (ReferenceIntegrityError if case == "native_bytes" else
                         ValueError if case == "native_fingerprint" else V2GradingInputRefused)
        with pytest.raises(expected_type) as caught:
            preparation._result(arguments["result_path"], arguments["expected_result_identity"],
                                arguments["observation"], seed.plan, arguments["deliverables_root"])
        reason = (f"reference file hash mismatch: {arguments['result_path']}" if case == "native_bytes" else
                  "inference result fingerprint does not match payload" if case == "native_fingerprint" else
                  semantic_errors[case])
        assert caught.value.args == (reason,)
        with pytest.raises(preparation.GradingPreparationRefused) as caught:
            preparation.prepare_observation_grading(seed.plan, **arguments)
        assert caught.value.args == ("time_budget_grading_preparation_refused",)
        _unpublished(arguments)
    else:
        marker = preparation.prepare_observation_grading(seed.plan, **arguments)
        output = arguments["destination"]
        assert marker == json.loads((output / preparation.READY).read_bytes())
        assert marker["observation"] == asdict(arguments["observation"]) == prepared["observation"]
        assert marker["inputs"] == prepared["inputs"]
        assert marker["result_identity"] == arguments["expected_result_identity"]
        assert marker["result"]["result_fingerprint"] == payload["result_fingerprint"]
        assert marker["result"]["status"] == status
        assert (output / preparation.RESULT).read_bytes() == original_result
        retained = json.loads((output / preparation.RESULT).read_bytes())
        assert retained == payload
        assert marker["launch_allowed"] is marker["execution_enabled"] is False
        assert marker["grading_attempt"] == 1
        assert marker["grading_policy"] == {"attempts_per_resulting_observation": 1,
            "failed_or_missing_outcomes": "retain", "regrade_for_score": False}
        config = json.loads((output / preparation.CONFIG).read_bytes())
        template = load_plan(seed.frozen / GRADER)
        assert all(config[key] == template[key] for key in ("judge", "prompt", "grader"))
        assert config["rubric"] == {**template["rubric"],
            "revision": seed.plan["shared"]["grading"]["rubric_revision"], "cache_dir": "../data/gdpval-local"}
        assert marker["grader"]["template_source_sha256"] == registration.FROZEN_TEMPLATE_SHA256
        assert all((output / "source" / role).read_bytes() == data for role, data in frozen_bytes.items())
        for path, data in original_deliverables.items():
            role = path.relative_to(arguments["deliverables_root"])
            assert (output / preparation.UPLOAD / role).read_bytes() == data

    assert arguments["result_path"].read_bytes() == original_result
    assert all(path.read_bytes() == data for path, data in original_deliverables.items())
    assert all(path.read_bytes() == data for path, data in original_inputs.items())
    assert all((seed.frozen / role).read_bytes() == data for role, data in frozen_bytes.items())
    assert (handoff / registration.HANDOFF_READY).read_bytes() == preparation_bytes
    assert not handoff.with_name(handoff.name + registration.HANDOFF_CONSUMED_SUFFIX).exists()
    assert not (tmp_path / "unused-observation-store").exists()
    assert offline == []
