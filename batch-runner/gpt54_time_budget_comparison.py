"""Compile one prospective time-budget registration, never an execution recipe.

The legacy comparison validates the unchanged source, input and judge facts.
Its shared request/token caps and run identities are NOT inherited by this study.
No deadline, counter, dispatcher or launch authority is implemented here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from core.agentic_v2_preregistration import seal
from gpt54_comparison_preflight import (
    ENVELOPE,
    ROOT,
    DispatchPlanRefused,
    _canonical_json,
    compile_dispatch_plan,
    load_plan,
)

VERSION = "gpt54-sandboxv2-codex-time-budget-v1"
STUDY_ID = "gpt54_sandboxv2_codex_time_budget_v1"
PLAN = ROOT / ENVELOPE / "gpt54_sandboxv2_codex_time_budget_v1.yaml"
COMPILER = "batch-runner/gpt54_time_budget_comparison.py"
SOURCE_PROFILE = ENVELOPE + "gpt54_sandboxv2_codex_comparison_local_source.yaml"
SOURCE_PROFILE_SHA256 = "81b9930102a19f298dfbb5e45c8f0d39045b89512aa5dc9b4d5543312835cbbe"
ACCEPTED_BASE_SHA = "882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2"
ACCEPTED_BASE_TREE = "45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca"
RUN_ORDER = (
    ("sandbox_v2", "v2", 1), ("codex", "codex", 1),
    ("codex", "codex", 2), ("sandbox_v2", "v2", 2),
)
SHARED_FACTS = ("model", "dataset", "grading", "results", "cost")
MAX_MANIFEST_BYTES = 65_536
LAUNCH_BLOCKERS = (
    "time_budget_observation_deadline_not_integrated",
    "time_budget_dispatch_and_capture_not_integrated",
    "reviewed_source_bound_execution_direction_required",
    "served_identity_and_original_input_verification_required",
    "credentialed_ci_input_authority_unresolved",
)


class TimeBudgetRegistrationRefused(ValueError):
    """The separate, fixed registration is not valid offline evidence."""


class _RegistrationLoader(yaml.SafeLoader):
    """Reject ambiguous YAML in this new schema without changing legacy reads."""

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise TimeBudgetRegistrationRefused("manifest_alias")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise TimeBudgetRegistrationRefused("manifest_duplicate_or_nonstring_key")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _regular_bytes(path: Path) -> bytes:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise TimeBudgetRegistrationRefused("source_not_regular")
    return path.read_bytes()


def load_registration(path: Path = PLAN) -> dict[str, Any]:
    """Read bounded registration metadata only; no source or input acquisition."""
    try:
        if path.lstat().st_size > MAX_MANIFEST_BYTES:
            raise TimeBudgetRegistrationRefused("manifest_too_large")
        raw = _regular_bytes(path)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise TimeBudgetRegistrationRefused("manifest_too_large")
        value = yaml.load(raw.decode("utf-8"), Loader=_RegistrationLoader)
        if not isinstance(value, dict):
            raise TimeBudgetRegistrationRefused("manifest_not_object")
        return value
    except TimeBudgetRegistrationRefused:
        raise
    except (OSError, ValueError, yaml.YAMLError, RecursionError) as error:
        raise TimeBudgetRegistrationRefused("manifest_unreadable") from error


def _expect(label: str, actual: Any, expected: Any) -> None:
    # Canonical JSON preserves bool/int/float distinctions and rejects NaN.
    if _canonical_json(actual) != _canonical_json(expected):
        raise TimeBudgetRegistrationRefused(label)


def _policy() -> dict[str, Any]:
    """One fixed policy, not a caller-extensible policy framework."""
    return {
        "plan_version": VERSION,
        "study_id": STUDY_ID,
        "comparison": "configuration_bundle",
        "question": "Which tested GPT-5.4 configuration produces usable, graded work within the same external generation-time budget?",
        "scope": {
            "inference_concurrency": 1,
            "max_generation_observations": 20,
            "repeats_per_condition": 2,
            "external_attempts_per_observation": 1,
            "external_replay_allowed": False,
            "external_resume_allowed": False,
            "external_retry_allowed": False,
            "pool_with_other_studies": False,
        },
        "generation_budget": {
            "policy": "external_elapsed_time_v1",
            "seconds_per_observation": 1200,
            "starts_at": "first_generation_start",
            "includes": ["all_waits", "native_internal_recovery"],
            "deadline_action": "request_interruption",
            "local_cleanup_grace_seconds": 20,
            "cleanup_grace_recorded_separately": True,
            "max_planned_host_lifecycle_seconds": 1220,
            "remote_billing_bound": False,
            "server_side_cancellation_guaranteed": False,
        },
        "native_measurements": {
            "policy": "observation_only_when_available",
            "metrics": ["model_attempt_count", "repeated_request_count", "input_tokens",
                        "output_tokens", "written_tokens", "native_retries"],
            "unavailable": "explicitly_unavailable_not_zero_or_estimated",
            "token_accounting": "difference_cumulative_totals_not_sum_snapshots",
            "cached_input_and_reasoning": "subsets_not_additional_tokens",
            "incomplete_usage": "preserve_null_and_partial_reasons",
            "shared_native_request_token_hard_caps": False,
            "native_turn_equals_model_attempt": False,
        },
        "grading_policy": {
            "attempts_per_resulting_observation": 1,
            "failed_or_missing_outcomes": "retain",
            "regrade_for_score": False,
        },
        "decision_rule": {
            "analysis": "descriptive_paired_outcome_and_grade_differences",
            "pairing": ["task_id", "repeat"],
            "spread": "within_condition_across_fixed_observations",
            "early_selection": False,
            "score_dependent_repeats": False,
            "precise_uncertainty_claim": False,
            "isolated_harness_causality_claim": False,
            "equal_native_compute_claim": False,
        },
        "launch_enabled": False,
        "execution_enabled": False,
    }


@dataclass(frozen=True)
class TimeBudgetRunSpec:
    """Observation identities only: no command, materializer or runtime config."""

    run_id: str
    condition: Literal["sandbox_v2", "codex"]
    repeat: int
    task_ids: tuple[str, ...]


@dataclass(frozen=True)
class CompiledTimeBudgetRegistration:
    manifest_sha256: str
    source_evidence_json: str
    intent_json: str
    runs: tuple[TimeBudgetRunSpec, ...]

    def as_dict(self) -> dict[str, Any]:
        intent = json.loads(self.intent_json)
        intent["runs"] = json.loads(_canonical_json([asdict(run) for run in self.runs]))
        return {
            "plan_version": "gpt54-offline-time-budget-registration-v1",
            "manifest_sha256": self.manifest_sha256,
            "source_evidence": json.loads(self.source_evidence_json),
            "registered_intent": intent,
            "implementation_status": {
                "registration_compiler": "implemented_offline",
                "generation_deadline": "not_integrated",
                "cleanup_grace": "not_integrated",
                "native_measurement_availability": "not_verified",
                "executor_enforces_registered_policy": False,
                "dispatch_and_capture": "not_integrated_for_this_study",
                "observations_executed_by_compiler": 0,
            },
            "launch_authority": {
                "launch_allowed": False,
                "execution_enabled": False,
                "full_220_allowed": False,
                "blockers": list(LAUNCH_BLOCKERS),
            },
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.as_dict()).encode("utf-8")


def compile_registration(plan: dict[str, Any]) -> CompiledTimeBudgetRegistration:
    """Validate fixed intent and real source facts; never produce launch recipes.

    The unmodified legacy compiler checks all 37 sources, score-free cohort,
    input versions and the real whole grader TEMPLATE closure. Only the named
    model/data/judge/result/cost facts and per-harness settings are reused. Its
    old shared caps, run IDs, dispatch commands and launch policy stay separate.
    """
    try:
        plan = json.loads(_canonical_json(plan))
        expected = _policy()
        keys = set(expected) | {"source_basis", "shared", "conditions", "runs"}
        if not isinstance(plan, dict) or set(plan) != keys:
            raise TimeBudgetRegistrationRefused("manifest_fields")
        for name, value in expected.items():
            _expect(name, plan[name], value)

        profile_bytes = _regular_bytes(ROOT / SOURCE_PROFILE)
        if hashlib.sha256(profile_bytes).hexdigest() != SOURCE_PROFILE_SHA256:
            raise TimeBudgetRegistrationRefused("source_profile_bytes")
        basis = {
            "accepted_base_sha": ACCEPTED_BASE_SHA,
            "accepted_base_tree": ACCEPTED_BASE_TREE,
            "source_profile": {"path": SOURCE_PROFILE, "sha256": SOURCE_PROFILE_SHA256},
            "registration_compiler": {
                "path": COMPILER,
                "sha256": hashlib.sha256(_regular_bytes(ROOT / COMPILER)).hexdigest(),
            },
        }
        _expect("source_basis", plan["source_basis"], basis)
        profile = load_plan(ROOT / SOURCE_PROFILE)
        dispatch = compile_dispatch_plan(profile)
        # Re-read the exact profile, not a mutable caller-supplied projection.
        if _regular_bytes(ROOT / SOURCE_PROFILE) != profile_bytes:
            raise TimeBudgetRegistrationRefused("source_profile_changed")
        controls = json.loads(dispatch.controls_json)
        shared = {name: controls[name] for name in SHARED_FACTS}
        _expect("shared_facts", plan["shared"], shared)
        conditions = {
            "sandbox_v2": {
                "template": profile["conditions"]["sandbox_v2"]["template"],
                "harness": "agentic_sandbox_v2",
                "isolation": "same-host",
                "replay_format": "faithful",
                "request": profile["conditions"]["sandbox_v2"]["request"],
                "local_settings": {name: controls["limits"][name] for name in (
                    "max_model_turns", "max_written_tokens_per_turn",
                )},
                "settings_scope": "v2_only_not_shared_native_compute",
            },
            "codex": {
                "template": profile["conditions"]["codex"]["template"],
                "harness": "codex",
                "sdk_version": profile["conditions"]["codex"]["sdk_version"],
                "cli_version": profile["conditions"]["codex"]["cli_version"],
                "request": profile["conditions"]["codex"]["request"],
                "provider_retry_settings": {name: controls["limits"][name] for name in (
                    "request_max_retries", "stream_max_retries",
                )},
                "retry_settings_bound_all_native_recovery": False,
                "native_turn_is_v2_turn_equivalent": False,
            },
        }
        _expect("condition_settings", plan["conditions"], conditions)
        task_ids = tuple(task["task_id"] for task in shared["dataset"]["tasks"])
        runs = tuple(TimeBudgetRunSpec(
            f"gpt54_time_budget_v1_{suffix}_r{repeat}", condition, repeat, task_ids,
        ) for condition, suffix, repeat in RUN_ORDER)
        _expect("repetition_matrix", plan["runs"], [
            {"run_id": run.run_id, "condition": run.condition,
             "repeat": run.repeat, "task_count": len(run.task_ids)} for run in runs
        ])
        intent = {name: plan[name] for name in expected if name not in (
            "launch_enabled", "execution_enabled",
        )}
        intent.update(shared=shared, conditions=conditions)
        return CompiledTimeBudgetRegistration(
            manifest_sha256=seal(plan),
            source_evidence_json=_canonical_json({
                "basis": basis, "validated_source_pins": json.loads(dispatch.source_pins_json),
                "source_profile_semantic_sha256": dispatch.manifest_sha256,
                "private_originals_verified": False,
                "template_not_materialized_grader": True,
            }),
            intent_json=_canonical_json(intent), runs=runs,
        )
    except TimeBudgetRegistrationRefused:
        raise
    except DispatchPlanRefused as error:
        raise TimeBudgetRegistrationRefused("source_contract_refused") from error
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError, RecursionError) as error:
        raise TimeBudgetRegistrationRefused("registration_cannot_be_compiled") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=PLAN)
    args = parser.parse_args(argv)
    try:
        report = {"registration_valid": True, "compiled": compile_registration(
            load_registration(args.manifest),
        ).as_dict()}
    except TimeBudgetRegistrationRefused as error:
        report = {"registration_valid": False, "reason": str(error), "compiled": None}
    print(_canonical_json(report))
    # A valid offline registration is deliberately not a successful launch gate.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
