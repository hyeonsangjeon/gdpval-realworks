"""Compile the prospective registration or prepare one observation, never launch.

The explicit dual-root mode separates reviewed runtime facts from the frozen
whole-closure judge. The omitted mode retains the legacy source refusal. Neither
mode selects an executor or grants launch authority. The separate explicit
preparation API verifies supplied local inputs and emits one model-free handoff.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import yaml

from core.agentic_v2_preregistration import seal
from gpt54_comparison_preflight import (
    ENVELOPE,
    ROOT,
    DispatchPlanRefused,
    GRADER,
    REQUIRED_SOURCES,
    V2_TEMPLATE,
    CODEX_TEMPLATE,
    _canonical_json,
    compile_dispatch_plan,
    load_plan,
)

VERSION = "gpt54-sandboxv2-codex-time-budget-v1"
STUDY_ID = "gpt54_sandboxv2_codex_time_budget_v1"
PLAN = ROOT / ENVELOPE / "gpt54_sandboxv2_codex_time_budget_v1.yaml"
COMPILER = "batch-runner/gpt54_time_budget_comparison.py"
SOURCE_PROFILE = ENVELOPE + "gpt54_sandboxv2_codex_comparison_local_source.yaml"
SOURCE_PROFILE_SHA256 = (
    "81b9930102a19f298dfbb5e45c8f0d39045b89512aa5dc9b4d5543312835cbbe"
)
ACCEPTED_BASE_SHA = "882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2"
ACCEPTED_BASE_TREE = "45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca"
FROZEN_TEMPLATE_SHA256 = (
    "37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce"
)
RUNTIME_ADDITIONS = {
    COMPILER,
    "batch-runner/ghcp_vm_input_bundle.py",
    "batch-runner/core/time_budget_observation_deadline.py",
    "batch-runner/core/agentic_v2_conversation.py",
    "batch-runner/core/agentic_v2_runner.py",
}
CHANGED_RUNTIME_SOURCES = RUNTIME_ADDITIONS | {
    "batch-runner/core/codex_runner.py",
    "batch-runner/core/agentic_v2_conversation_runner.py",
}
REGISTRATION_PATH = ENVELOPE + "gpt54_sandboxv2_codex_time_budget_v1.yaml"
RUN_ORDER = (
    ("sandbox_v2", "v2", 1),
    ("codex", "codex", 1),
    ("codex", "codex", 2),
    ("sandbox_v2", "v2", 2),
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
HANDOFF_CONFIG = "configuration.json"
HANDOFF_TASK = "task.json"
HANDOFF_READY = "preparation.json"
HANDOFF_RESERVATION_SUFFIX = ".time-budget-preparation-reserved.json"


class TimeBudgetRegistrationRefused(ValueError):
    """The separate, fixed registration is not valid offline evidence."""


class TimeBudgetPreparationRefused(TimeBudgetRegistrationRefused):
    """One local observation cannot be published; partial output is not reusable."""


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
                raise TimeBudgetRegistrationRefused(
                    "manifest_duplicate_or_nonstring_key"
                )
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
            "metrics": [
                "model_attempt_count",
                "repeated_request_count",
                "input_tokens",
                "output_tokens",
                "written_tokens",
                "native_retries",
            ],
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
    runtime_bound: bool = False

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
                "generation_deadline": "opt_in_host_control"
                if self.runtime_bound
                else "not_integrated",
                "cleanup_grace": "one_absolute_cleanup_deadline"
                if self.runtime_bound
                else "not_integrated",
                "host_control_selected_by_executor": False,
                "native_measurement_availability": "not_verified",
                "executor_enforces_registered_policy": False,
                "dispatch_and_capture": "not_integrated_for_this_study",
                "observations_executed_by_compiler": 0,
            },
            "launch_authority": {
                "launch_allowed": False,
                "execution_enabled": False,
                "full_220_allowed": False,
                "blockers": (
                    [
                        "time_budget_dispatch_must_select_observation_control",
                        *LAUNCH_BLOCKERS[1:],
                    ]
                    if self.runtime_bound
                    else list(LAUNCH_BLOCKERS)
                ),
            },
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.as_dict()).encode("utf-8")


@contextmanager
def _reviewed_source(root: Path, expected_sha: str, roles: set[str]):
    """Read held regular bytes against an independent, full Git commit anchor.

    Git's tree object supplies blob identities, never local markers or the
    index. Hashing canonical Git blob bytes checks that exact object identity;
    it does not invent or replace the whole-grader fingerprint below.
    """
    from gpt54_disposable_checkout import (
        _git,
        _repository,
        _runtime_revision,
        _safe_checkout_configuration,
    )
    from gpt54_run_config_bundle import _held_parents, _path
    from gpt54_prepared_input_attestation import _identity, _read_bytes

    if (
        type(expected_sha) is not str
        or re.fullmatch(r"[0-9a-f]{40}", expected_sha) is None
    ):
        raise TimeBudgetRegistrationRefused("review_anchor_must_be_full_commit")
    root, _ = _repository(root)
    _safe_checkout_configuration(root)
    if _git(
        root, "rev-parse", "--verify", "--end-of-options", expected_sha + "^{commit}"
    ).stdout != (expected_sha + "\n").encode("ascii"):
        raise TimeBudgetRegistrationRefused("review_anchor_not_commit")
    tree = (
        _git(
            root, "rev-parse", "--verify", "--end-of-options", expected_sha + "^{tree}"
        )
        .stdout.decode()
        .strip()
    )
    _runtime_revision(root, expected_sha, tree)
    entries = _git(
        root,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        expected_sha,
        "--",
        *sorted(roles),
        "batch-runner/core",
    ).stdout
    if len(entries) > 2 * 1024 * 1024:
        raise TimeBudgetRegistrationRefused("source_inventory_bound")
    objects = {}
    for row in entries.rstrip(b"\0").split(b"\0"):
        metadata, name = row.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        name = name.decode("utf-8")
        if name not in roles and not (
            name.startswith("batch-runner/core/") and name.endswith(".py")
        ):
            continue
        if mode not in (b"100644", b"100755") or kind != b"blob" or name in objects:
            raise TimeBudgetRegistrationRefused("source_requires_regular_tracked_blob")
        objects[name] = oid.decode("ascii")
    if not roles.issubset(objects):
        raise TimeBudgetRegistrationRefused("source_missing_tracked_blob")

    def core_inventory():
        found = set()
        for path in (root / "batch-runner/core").rglob("*"):
            if path.is_symlink():
                raise TimeBudgetRegistrationRefused("source_symlink")
            if path.is_file() and path.suffix == ".py":
                found.add(path.relative_to(root).as_posix())
        _expect(
            "source_core_inventory",
            sorted(found),
            sorted(
                name
                for name in objects
                if name.startswith("batch-runner/core/") and name.endswith(".py")
            ),
        )

    with _held_parents(root, tuple(objects)) as held:
        core_inventory()
        identities = {}
        total = 0
        for name, oid in sorted(objects.items()):
            path = _path(root, name)
            size = path.lstat().st_size
            total += size
            if size > 8 * 1024 * 1024 or total > 64 * 1024 * 1024:
                raise TimeBudgetRegistrationRefused("source_bytes_bound")
            data = _read_bytes(path, size=size)
            blob = hashlib.sha1(
                b"blob " + str(len(data)).encode("ascii") + b"\0" + data
            ).hexdigest()
            if blob != oid:
                raise TimeBudgetRegistrationRefused("source_differs_from_reviewed_blob")
            identities[name] = _identity(data)
        yield root, tree, identities
        for name, identity in identities.items():
            _read_bytes(_path(root, name), **identity)
        core_inventory()
        held()
        _runtime_revision(root, expected_sha, tree)


def _frozen_roles() -> set[str]:
    # F has this sealed two-file requirements graph. Bind its bytes to tracked
    # blobs BEFORE the unchanged whole-closure helper follows any include.
    # This is a source-read boundary, not a change to the hash algorithm/scope.
    return set(REQUIRED_SOURCES) | {
        SOURCE_PROFILE,
        "batch-runner/prompts/grader_judge.md",
        "batch-runner/prompts/grader_judge_v2.md",
        "batch-runner/scripts/download_inference_from_hf.py",
        "batch-runner/requirements.txt",
        "batch-runner/requirements-renderer.txt",
    }


@contextmanager
def _dual_root_sources(
    plan,
    runtime_root,
    expected_reviewed_source_sha,
    frozen_grader_root,
    expected_grader_source_sha,
):
    from core.agentic_v2_conversation_runner import ceilings_from
    from core.execution_envelope_tasks import (
        catalog_sha256,
        load_task_catalog,
        select_advance_check_tasks,
    )
    from gpt54_run_config_bundle import _root, _sources
    from step8_grade import compute_grader_source_hash

    if expected_grader_source_sha != ACCEPTED_BASE_SHA:
        raise TimeBudgetRegistrationRefused("frozen_grader_review_anchor")
    runtime_root, frozen_grader_root = _root(runtime_root), _root(frozen_grader_root)
    if runtime_root == frozen_grader_root:
        raise TimeBudgetRegistrationRefused(
            "runtime_and_frozen_grader_roots_must_differ"
        )
    _expect(
        "runtime_source_pin_set",
        sorted(plan["source_pins"]),
        sorted(REQUIRED_SOURCES | RUNTIME_ADDITIONS),
    )
    with (
        _reviewed_source(
            runtime_root,
            expected_reviewed_source_sha,
            REQUIRED_SOURCES | RUNTIME_ADDITIONS | {REGISTRATION_PATH},
        ) as (runtime, runtime_tree, _),
        _reviewed_source(
            frozen_grader_root,
            expected_grader_source_sha,
            _frozen_roles(),
        ) as (frozen, frozen_tree, _),
    ):
        _expect("frozen_grader_tree", frozen_tree, ACCEPTED_BASE_TREE)
        # Verify the sealed historical profile in F. Never relabel R with its
        # whole-core template identity or call the legacy compiler against R.
        profile_bytes = _regular_bytes(frozen / SOURCE_PROFILE)
        _expect(
            "source_profile_bytes",
            hashlib.sha256(profile_bytes).hexdigest(),
            SOURCE_PROFILE_SHA256,
        )
        profile = load_plan(frozen / SOURCE_PROFILE)
        frozen_sources = _sources(frozen, profile, SOURCE_PROFILE)
        expected_pins = dict(profile["source_pins"])
        expected_pins.update(
            {
                name: hashlib.sha256(_regular_bytes(runtime / name)).hexdigest()
                for name in CHANGED_RUNTIME_SOURCES
            }
        )
        _expect("runtime_source_roles", plan["source_pins"], expected_pins)
        runtime_manifest = load_registration(runtime / REGISTRATION_PATH)
        runtime_sources = _sources(runtime, runtime_manifest, REGISTRATION_PATH)
        _expect(
            "running_compiler_bytes",
            hashlib.sha256(_regular_bytes(runtime / COMPILER)).hexdigest(),
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        )
        basis = {
            "accepted_base_sha": ACCEPTED_BASE_SHA,
            "accepted_base_tree": ACCEPTED_BASE_TREE,
            "source_profile": {"path": SOURCE_PROFILE, "sha256": SOURCE_PROFILE_SHA256},
            "registration_compiler": {
                "path": COMPILER,
                "sha256": hashlib.sha256(
                    _regular_bytes(runtime / COMPILER)
                ).hexdigest(),
            },
            "runtime_role": "independently_reviewed_runtime_commit",
            "frozen_grader": {
                "source_sha": ACCEPTED_BASE_SHA,
                "source_tree": ACCEPTED_BASE_TREE,
                "template_path": GRADER,
                "template_source_sha256": FROZEN_TEMPLATE_SHA256,
                "execution_source": "frozen_source_only_not_runtime_root",
                "materialized_config_requires_distinct_path_bytes_and_fingerprint": True,
            },
        }
        _expect("source_basis", plan["source_basis"], basis)
        grader = load_plan(frozen / GRADER)
        template = compute_grader_source_hash(
            config_path=frozen / GRADER,
            config=grader,
            batch_root=frozen / "batch-runner",
        )
        _expect("frozen_whole_template", template, FROZEN_TEMPLATE_SHA256)
        shared = {name: profile["shared"][name] for name in SHARED_FACTS}
        _expect(
            "frozen_grader_template",
            shared["grading"]["template_source_sha256"],
            template,
        )
        # Root-explicit catalog and typed harness controls verify current facts;
        # no fabricated ComparisonGradingPlan and no production ROOT mutation.
        catalog_path = runtime / ENVELOPE / "gdpval_task_catalog.json"
        catalog = load_task_catalog(catalog_path)
        selected = select_advance_check_tasks(catalog)
        by_id = catalog.by_task_id()
        dataset = shared["dataset"]
        _expect(
            "runtime_catalog", dataset["catalog_sha256"], catalog_sha256(catalog_path)
        )
        _expect(
            "runtime_cohort",
            dataset["tasks"],
            [
                {"task_id": task, "prompt_sha256": by_id[task].prompt_sha256}
                for task in selected.task_ids
            ],
        )
        v2 = load_plan(runtime / V2_TEMPLATE)
        codex = load_plan(runtime / CODEX_TEMPLATE)
        _expect(
            "runtime_model",
            codex["condition_a"]["model"]["deployment"],
            v2["model"]["deployment"],
        )
        limits = ceilings_from(
            v2, SimpleNamespace(**v2["cost"]["chosen_settings"])
        ).as_dict()
        for name in ("max_model_turns", "max_written_tokens_per_turn"):
            _expect(
                "runtime_local_setting", limits[name], profile["shared"]["limits"][name]
            )
        controls = {**shared, "limits": profile["shared"]["limits"]}
        evidence = {
            "basis": basis,
            "runtime": {
                "source_sha": expected_reviewed_source_sha,
                "source_tree": runtime_tree,
                **runtime_sources,
            },
            "frozen_grader": {
                "source_sha": expected_grader_source_sha,
                "source_tree": frozen_tree,
                "template_source_sha256": template,
                "template_config_path": GRADER,
                "materialized_config_path": None,
                "materialized_grader_source_sha256": None,
                "execution_source": "frozen_source_only_not_runtime_root",
                **frozen_sources,
            },
            "validated_source_pins": plan["source_pins"],
            "source_profile_semantic_sha256": seal(profile),
            "private_originals_verified": False,
            "template_not_materialized_grader": True,
        }
        yield profile, controls, basis, evidence
        _expect("registered_manifest", plan, runtime_manifest)


def compile_registration(
    plan: dict[str, Any],
    *,
    runtime_root: Path | None = None,
    expected_reviewed_source_sha: str | None = None,
    frozen_grader_root: Path | None = None,
    expected_grader_source_sha: str | None = None,
) -> CompiledTimeBudgetRegistration:
    """Validate fixed intent and real source facts; never produce launch recipes.

    The unmodified legacy compiler checks all 37 sources, score-free cohort,
    input versions and the real whole grader TEMPLATE closure. Only the named
    model/data/judge/result/cost facts and per-harness settings are reused. Its
    old shared caps, run IDs, dispatch commands and launch policy stay separate.
    """
    try:
        anchors = (
            runtime_root,
            expected_reviewed_source_sha,
            frozen_grader_root,
            expected_grader_source_sha,
        )
        anchored = any(value is not None for value in anchors)
        if anchored and any(value is None for value in anchors):
            raise TimeBudgetRegistrationRefused(
                "both_independent_review_anchors_required"
            )
        with ExitStack() as sources:
            return _compile_registration(plan, anchors, anchored, sources)
    except TimeBudgetRegistrationRefused:
        raise
    except DispatchPlanRefused as error:
        raise TimeBudgetRegistrationRefused("source_contract_refused") from error
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        yaml.YAMLError,
        RecursionError,
    ) as error:
        raise TimeBudgetRegistrationRefused(
            "registration_cannot_be_compiled"
        ) from error


def _compile_registration(plan, anchors, anchored, sources):
    try:
        plan = json.loads(_canonical_json(plan))
        expected = _policy()
        keys = set(expected) | {"source_basis", "shared", "conditions", "runs"}
        if anchored:
            keys.add("source_pins")
        if not isinstance(plan, dict) or set(plan) != keys:
            raise TimeBudgetRegistrationRefused("manifest_fields")
        for name, value in expected.items():
            _expect(name, plan[name], value)

        if anchored:
            profile, controls, basis, evidence = sources.enter_context(
                _dual_root_sources(plan, *anchors)
            )
        else:
            profile, controls, basis, evidence = _legacy_sources(plan)
        shared = {name: controls[name] for name in SHARED_FACTS}
        return _compile_intent(
            plan, expected, profile, controls, basis, evidence, shared, anchored
        )
    except TimeBudgetRegistrationRefused:
        raise
    except DispatchPlanRefused as error:
        raise TimeBudgetRegistrationRefused("source_contract_refused") from error


def _legacy_sources(plan):
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
    return (
        profile,
        controls,
        basis,
        {
            "basis": basis,
            "validated_source_pins": json.loads(dispatch.source_pins_json),
            "source_profile_semantic_sha256": dispatch.manifest_sha256,
            "private_originals_verified": False,
            "template_not_materialized_grader": True,
        },
    )


def _compile_intent(
    plan, expected, profile, controls, basis, evidence, shared, anchored
):
    _expect("shared_facts", plan["shared"], shared)
    conditions = {
        "sandbox_v2": {
            "template": profile["conditions"]["sandbox_v2"]["template"],
            "harness": "agentic_sandbox_v2",
            "isolation": "same-host",
            "replay_format": "faithful",
            "request": profile["conditions"]["sandbox_v2"]["request"],
            "local_settings": {
                name: controls["limits"][name]
                for name in (
                    "max_model_turns",
                    "max_written_tokens_per_turn",
                )
            },
            "settings_scope": "v2_only_not_shared_native_compute",
        },
        "codex": {
            "template": profile["conditions"]["codex"]["template"],
            "harness": "codex",
            "sdk_version": profile["conditions"]["codex"]["sdk_version"],
            "cli_version": profile["conditions"]["codex"]["cli_version"],
            "request": profile["conditions"]["codex"]["request"],
            "provider_retry_settings": {
                name: controls["limits"][name]
                for name in (
                    "request_max_retries",
                    "stream_max_retries",
                )
            },
            "retry_settings_bound_all_native_recovery": False,
            "native_turn_is_v2_turn_equivalent": False,
        },
    }
    _expect("condition_settings", plan["conditions"], conditions)
    task_ids = tuple(task["task_id"] for task in shared["dataset"]["tasks"])
    runs = tuple(
        TimeBudgetRunSpec(
            f"gpt54_time_budget_v1_{suffix}_r{repeat}",
            condition,
            repeat,
            task_ids,
        )
        for condition, suffix, repeat in RUN_ORDER
    )
    _expect(
        "repetition_matrix",
        plan["runs"],
        [
            {
                "run_id": run.run_id,
                "condition": run.condition,
                "repeat": run.repeat,
                "task_count": len(run.task_ids),
            }
            for run in runs
        ],
    )
    intent = {
        name: plan[name]
        for name in expected
        if name
        not in (
            "launch_enabled",
            "execution_enabled",
        )
    }
    intent.update(shared=shared, conditions=conditions)
    return CompiledTimeBudgetRegistration(
        manifest_sha256=seal(plan),
        source_evidence_json=_canonical_json(evidence),
        intent_json=_canonical_json(intent),
        runs=runs,
        runtime_bound=anchored,
    )


@contextmanager
def _observation_input_registration(root, expected_sha, manifest_path, dataset):
    """Reuse only input facts, never the old registration's dispatch authority."""
    from core.execution_envelope_tasks import (
        catalog_sha256, check_catalog_carries_no_scores, load_task_catalog,
        select_advance_check_tasks,
    )
    from gpt54_run_config_bundle import _manifest_file, _root
    from gpt54_v2_grading_input import _read_bytes

    root = _root(root)
    manifest = _manifest_file(root, manifest_path)
    catalog_role = ENVELOPE + "gdpval_task_catalog.json"
    envelope_role = ENVELOPE + "advance_check_plan.yaml"
    roles = {manifest_path, catalog_role, envelope_role}
    with _reviewed_source(root, expected_sha, roles) as (_, tree, identities):
        # The frozen input document genuinely uses YAML &shared aliases. Its
        # exact reviewed blob and input-fact equality are checked; do not apply
        # the separate prospective schema's no-alias rule to that old format.
        document = yaml.safe_load(_read_bytes(manifest, **identities[manifest_path]))
        for name in (catalog_role, envelope_role):
            _read_bytes(root / name, sha256=document["source_pins"][name])
        _expect("input_catalog_score_free", check_catalog_carries_no_scores(root / catalog_role), [])
        catalog = load_task_catalog(root / catalog_role)
        digest = catalog_sha256(root / catalog_role)
        task_ids = select_advance_check_tasks(catalog, catalog_fingerprint=digest).task_ids
        by_id = catalog.by_task_id()
        envelope = load_plan(root / envelope_role)
        actual = {
            "repo_id": catalog.dataset_repo_id, "revision": catalog.dataset_revision,
            "parquet_sha256": catalog.dataset_file_sha256, "catalog_sha256": digest,
            "cohort": "advance_check_5",
            "tasks": [{"task_id": task, "prompt_sha256": by_id[task].prompt_sha256} for task in task_ids],
            "input_file_versions": envelope["model_run_conditions"]["shared"]["input_file_versions"],
        }
        _expect("input_registration_dataset", document["shared"]["dataset"], actual)
        _expect("study_input_dataset", actual, dataset)
        yield catalog, task_ids, {
            "source_sha": expected_sha, "source_tree": tree,
            "scope": "dataset_and_cohort_only_not_legacy_dispatch",
            "files": {name: identities[name] for name in sorted(roles)},
            "manifest_path": manifest_path,
        }


def _observation_inputs(dataset, catalog, task_ids, *, parquet, references, step0):
    """Read real bytes through the existing input-only projection validators."""
    from core.agentic_v2_manifest_binding import bind_stage
    from core.source_identity import source_task_projection_sha256
    from gpt54_prepared_input_attestation import (
        _SourceSnapshot, _dataset_tasks, _identity, _reference_snapshot,
    )
    from gpt54_run_input_bundle import _step0_bytes
    from gpt54_v2_grading_input import _read_bytes

    data = _read_bytes(parquet, sha256=dataset["parquet_sha256"])
    projections, needs_files = _dataset_tasks(data, task_ids)
    bound = bind_stage(
        dataset["cohort"], dataset_tasks=[SimpleNamespace(**row) for row in projections],
        catalog=catalog, catalog_digest=dataset["catalog_sha256"],
    )
    versions = dict(dataset["input_file_versions"])
    _expect("input_dataset_version", versions.pop(dataset["repo_id"] + "@" + dataset["revision"]),
            dataset["parquet_sha256"])
    paths = [name for row in projections for name in row["reference_files"]]
    if len(paths) != len(set(paths)):
        raise TimeBudgetPreparationRefused("duplicate_or_cross_task_reference_path")
    _expect("input_reference_set", sorted(paths), sorted(versions))
    records = _reference_snapshot(references, versions)
    sources = [{
        "projection": row,
        "source_projection_sha256": source_task_projection_sha256(**row),
        "text_bytes": {name: _identity(row[name].encode("utf-8"))
                       for name in ("prompt", "rubric_json", "rubric_pretty")},
        "reference_file_records": [{"path": name, **records[name]} for name in row["reference_files"]],
    } for row in projections]
    snapshot = _SourceSnapshot(
        {"dataset": {"parquet": _identity(data)}, "needs_files_policy": "deliverable_only"},
        sources, projections, records, needs_files, bound,
    )
    # None returns without a read. V2 never consumes Codex's Step0 input.
    manifest = _step0_bytes(step0, snapshot)
    return snapshot, None if manifest is None else _identity(manifest)


def _observation_configuration(plan, run, task_id, runtime_root):
    """Real template-derived factory inputs, not a standalone dispatch config."""
    from core.agentic_v2_contract import AgenticV2Profile
    from core.agentic_v2_conversation_runner import ceilings_from
    from core.codex_runtime_config import DEFAULT_PROVIDER_ID
    from core.experiment_config import ExperimentConfig

    model = plan["shared"]["model"]
    condition = plan["conditions"][run.condition]
    config = load_plan(runtime_root / condition["template"])
    if run.condition == "sandbox_v2":
        # Project the actual factory/voice settings, not the old stage plan's
        # dollar approvals, escalation, grading or dispatch instructions.
        template = config
        config = {name: template[name] for name in (
            "model", "azure_connection", "instructions", "fixed_settings", "safety_blocks_must_stay_closed",
        )}
        config["cost"] = {"chosen_settings": template["cost"]["chosen_settings"]}
        config["profile"] = asdict(AgenticV2Profile.from_mapping({
            "tool_contract_version": "2.0", "policy_profile_id": template.get("policy_profile_id") or "offline-full-v1",
            "foundation_only": True,
        }))
        config["model"].update(deployment=model["deployment"], resolved_model=model["resolved_model"],
                               **condition["request"])
        config["azure_connection"].update(account=model["account"], route_profile=model["route_profile"])
        config["task_ids"] = [task_id]
        config["fixed_settings"].update(
            retry_max_attempts=1, self_review_enabled=False, self_review_max_attempts=0,
            per_task_timeout_seconds=1200, replay_format=condition["replay_format"],
        )
        limits = ceilings_from(config, SimpleNamespace(**config["cost"]["chosen_settings"])).as_dict()
        _expect("v2_local_settings", {name: limits[name] for name in condition["local_settings"]},
                condition["local_settings"])
        factory = "core.agentic_v2_conversation_runner.build_runner_factory"
        argument = "observation_for"
    else:
        config["experiment"].update(
            id=run.run_id, name=f"GPT-5.4 time-budget Codex repeat {run.repeat}",
            description="One model-free observation handoff; launch remains blocked.",
        )
        config["data"]["source"] = plan["shared"]["dataset"]["repo_id"]
        config["data"]["filter"]["task_ids"] = [task_id]
        config["condition_a"]["model"].update(
            provider=model["provider"], deployment=model["deployment"], reasoning_effort=model["reasoning_effort"],
        )
        config["execution"]["codex"].update(
            model=model["deployment"], provider_id=DEFAULT_PROVIDER_ID,
            **condition["request"], **condition["provider_retry_settings"],
        )
        config["execution"].update(timeout=1200, max_retries=0, resume_max_rounds=0)
        if ExperimentConfig.from_dict(config).validate():
            raise TimeBudgetPreparationRefused("codex_observation_configuration")
        factory, argument = "core.codex_runner.CodexAgentRunner", "observation_control"
    return config, factory, argument


def _handoff_path(value):
    from core.inference_manifest import _assert_no_symlink_ancestors

    path = Path(value)
    if ".." in path.parts:
        raise TimeBudgetPreparationRefused("handoff_parent_traversal")
    path = Path(os.path.abspath(path))
    _assert_no_symlink_ancestors(path)
    return path


def prepare_observation_handoff(
    plan: dict[str, Any], *, run_id: str, task_id: str,
    runtime_root: Path, expected_reviewed_source_sha: str,
    frozen_grader_root: Path, expected_grader_source_sha: str,
    input_registration_root: Path, expected_input_source_sha: str,
    input_registration_path: str, dataset_parquet: Path, reference_root: Path,
    destination: Path, step0_manifest: Path | None = None,
) -> dict[str, Any]:
    """Publish one config/task/reference handoff and final preparation evidence.

    All source anchors are caller-supplied full commits. The input registration
    supplies dataset/cohort facts only, after equality with the genuine study.
    Originals must already exist locally; no acquisition, Step1, provider,
    grading materialization, observation admission or clock start occurs here.
    V2 requires Step0 to be absent; Codex verifies its full canonical bytes.

    The destination must be new, disjoint from sources/inputs, with an existing
    parent. A retained sibling reservation refuses clobber/adoption after any
    partial write. Only the last preparation.json signals verified local bytes.
    It grants no launch authority. No historical API/default is changed.
    """
    from core.agentic_v2_manifest_binding import ManifestRefused
    from core.time_budget_observation_deadline import ObservationIdentity
    from ghcp_vm_input_bundle import _publication_parents, _write_no_clobber
    from gpt54_prepared_input_attestation import _identity
    from gpt54_run_config_bundle import _held_parents, _path
    from gpt54_v2_grading_input import _read_bytes

    try:
        anchors = (runtime_root, expected_reviewed_source_sha, frozen_grader_root, expected_grader_source_sha)
        if any(value is None for value in (*anchors, input_registration_root, expected_input_source_sha,
                                           input_registration_path)):
            raise TimeBudgetPreparationRefused("explicit_source_and_input_anchors_required")
        if type(run_id) is not str or type(task_id) is not str:
            raise TimeBudgetPreparationRefused("exactly_one_registered_observation_required")
        plan = json.loads(_canonical_json(plan))
        output = _handoff_path(destination)
        reservation = output.with_name(output.name + HANDOFF_RESERVATION_SUFFIX)
        if not output.parent.is_dir():
            raise TimeBudgetPreparationRefused("handoff_parent_required")

        def absent():
            if os.path.lexists(output) or os.path.lexists(reservation):
                raise TimeBudgetPreparationRefused("handoff_or_reservation_exists")

        absent()
        with ExitStack() as sources:
            compiled = _compile_registration(plan, anchors, True, sources)
            selected = [run for run in compiled.runs if run.run_id == run_id and task_id in run.task_ids]
            if len(selected) != 1:
                raise TimeBudgetPreparationRefused("exactly_one_registered_observation_required")
            run = selected[0]
            if (run.condition == "codex") != (step0_manifest is not None):
                raise TimeBudgetPreparationRefused("condition_specific_step0_required")
            parquet, references = _handoff_path(dataset_parquet), _handoff_path(reference_root)
            step0 = None if step0_manifest is None else _handoff_path(step0_manifest)
            for path in (runtime_root, frozen_grader_root, input_registration_root, parquet, references,
                         *(() if step0 is None else (step0,))):
                source = _handoff_path(path)
                if any(target.is_relative_to(source) or source.is_relative_to(target)
                       for target in (output, reservation)):
                    raise TimeBudgetPreparationRefused("handoff_source_overlap")
            dataset = plan["shared"]["dataset"]
            catalog, task_ids, input_source = sources.enter_context(_observation_input_registration(
                input_registration_root, expected_input_source_sha, input_registration_path, dataset,
            ))
            versions = {name: digest for name, digest in dataset["input_file_versions"].items()
                        if name.startswith("reference_files/")}
            checks = [sources.enter_context(_held_parents(parquet.parent, (parquet.name,))),
                      sources.enter_context(_held_parents(references, tuple(versions)))]
            if step0 is not None:
                checks.append(sources.enter_context(_held_parents(step0.parent, (step0.name,))))

            def read_inputs():
                return _observation_inputs(dataset, catalog, task_ids, parquet=parquet,
                                           references=references, step0=step0)

            snapshot, step0_identity = read_inputs()
            source = next(row for row in snapshot.sources if row["projection"]["task_id"] == task_id)
            task = source["projection"]
            inputs = {
                "registration": input_source,
                "dataset": {**snapshot.shared_binding["dataset"], "repo_id": dataset["repo_id"],
                            "revision": dataset["revision"], "catalog_sha256": dataset["catalog_sha256"]},
                "task_id": task_id, "source_projection_sha256": source["source_projection_sha256"],
                "text_bytes": source["text_bytes"], "reference_file_records": source["reference_file_records"],
                "needs_files_policy": "deliverable_only", "needs_files": snapshot.needs_files[task_id],
                "step0_manifest": step0_identity,
                "verification": "local_bytes_against_independently_anchored_input_registration",
            }
            evidence = json.loads(compiled.source_evidence_json)
            runtime = evidence["runtime"]
            identity = ObservationIdentity(
                STUDY_ID, run.run_id, run.condition, run.repeat, task_id,
                runtime["source_sha"], runtime["source_tree"], compiled.manifest_sha256, seal(inputs),
            )
            config, factory, argument = _observation_configuration(plan, run, task_id, Path(runtime_root))
            control = {
                "required": True, "type": "core.time_budget_observation_deadline.TimeBudgetObservation",
                "factory_argument": argument, "identity": asdict(identity),
                "generation_seconds": 1200, "cleanup_seconds": 20,
                "admission_reserved": False, "generation_started": False,
            }
            configuration = {
                "handoff_version": "gpt54-time-budget-observation-configuration-v1",
                "factory": factory, "configuration": config, "observation_control": control,
                "model_binding": plan["shared"]["model"],
                "launch_allowed": False, "execution_enabled": False,
            }
            if run.condition == "sandbox_v2":
                arguments = asdict(next(row for row in snapshot.bound.tasks if row.task_id == task_id))
                _expect("v2_reference_order", list(arguments["reference_files"]), task["reference_files"])
                kind = "sandbox_v2_task_to_run"
            else:
                arguments = {
                    "task_prompt": task["prompt"], "model": plan["shared"]["model"]["deployment"],
                    "reference_files": task["reference_files"], "occupation": task["occupation"],
                    "experiment_prompt": config["condition_a"]["prompt"], "run_id": run.run_id,
                    "condition_name": run.condition, "task_id": task_id,
                }
                kind = "codex_run_arguments"
            payload = {"kind": kind, "arguments": arguments, "reference_path_base": "handoff_directory",
                       "reference_file_records": source["reference_file_records"]}
            files = {
                HANDOFF_CONFIG: _canonical_json(configuration).encode("utf-8"),
                HANDOFF_TASK: _canonical_json(payload).encode("utf-8"),
                **{item["path"]: _read_bytes(references / item["path"], sha256=item["sha256"], size=item["size"])
                   for item in source["reference_file_records"]},
            }
            marker = {
                "preparation_version": "gpt54-time-budget-observation-preparation-v1",
                "observation": asdict(identity), "abba_index": compiled.runs.index(run),
                "registration_file": runtime["manifest_file"],
                "runtime_source": {name: runtime[name] for name in ("source_sha", "source_tree")},
                "frozen_grader": {name: evidence["frozen_grader"][name] for name in (
                    "source_sha", "source_tree", "template_source_sha256", "template_config_path",
                    "materialized_config_path", "materialized_grader_source_sha256", "execution_source",
                )},
                "condition_template": {"path": plan["conditions"][run.condition]["template"],
                                       **runtime["source_files"][plan["conditions"][run.condition]["template"]]},
                "inputs": inputs, "observation_control": control,
                "files": {name: _identity(data) for name, data in files.items()},
                "launch_authority": compiled.as_dict()["launch_authority"],
                "evidence_boundary": "model_free_one_observation_preparation_not_execution",
            }
            marker_data = _canonical_json(marker).encode("utf-8")
            reservation_data = _canonical_json({
                "reservation_version": "gpt54-time-budget-preparation-reservation-v1",
                "intended_preparation": _identity(marker_data), "ready_path": HANDOFF_READY,
            }).encode("utf-8")

            def reread_inputs():
                current, current_step0 = read_inputs()
                _expect("input_snapshot_changed", (current.sources, current.shared_binding, current.needs_files,
                                                   current.references, current_step0),
                        (snapshot.sources, snapshot.shared_binding, snapshot.needs_files,
                         snapshot.references, step0_identity))
                for check in checks:
                    check()

            reread_inputs()
            with _publication_parents(output.parent) as (check, mkdir, descriptor):
                absent()
                _write_no_clobber(reservation, reservation_data, parent_fd=descriptor(output.parent))
                mkdir(output)
                directories = {parent for name in files for parent in _path(output, name).parents
                               if parent != output and parent.is_relative_to(output)}
                for directory in sorted(directories, key=lambda path: (len(path.parts), path.as_posix())):
                    mkdir(directory)
                for name, data in files.items():
                    path = _path(output, name)
                    _write_no_clobber(path, data, parent_fd=descriptor(path.parent))
                reread_inputs()
                _read_bytes(reservation, **_identity(reservation_data))
                # Exit performs every held R/F/input-registration final reread
                # BEFORE readiness. No fallible source check follows the marker.
                sources.close()
                for name, data in files.items():
                    _read_bytes(_path(output, name), **_identity(data))
                members = tuple(output.rglob("*"))
                if any(path.is_symlink() for path in members):
                    raise TimeBudgetPreparationRefused("handoff_member_symlink")
                _expect("handoff_members", sorted(path.relative_to(output).as_posix() for path in members),
                        sorted([*files, *(path.relative_to(output).as_posix() for path in directories)]))
                check()
                _write_no_clobber(output / HANDOFF_READY, marker_data, parent_fd=descriptor(output))
            return marker
    except TimeBudgetRegistrationRefused:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration,
            ManifestRefused, yaml.YAMLError, RecursionError):
        raise TimeBudgetPreparationRefused("observation_handoff_refused") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=PLAN)
    args = parser.parse_args(argv)
    try:
        report = {
            "registration_valid": True,
            "compiled": compile_registration(
                load_registration(args.manifest),
            ).as_dict(),
        }
    except TimeBudgetRegistrationRefused as error:
        report = {"registration_valid": False, "reason": str(error), "compiled": None}
    print(_canonical_json(report))
    # A valid offline registration is deliberately not a successful launch gate.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
