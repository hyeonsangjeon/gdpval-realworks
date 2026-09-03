#!/usr/bin/env python3
"""Step 8: Grade inference outputs with rubric-based judge.

Usage:
    python step8_grade.py exp998_smoke_baseline_sample \
    --config grading_configs/default_v2_sol_max.yaml \
      --dry-run --limit 3
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import math
import os
import re
import signal
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import SchemaError, ValidationError

from core.azure_ai_clients import (
    canonical_deployment,
    grader_route_workloads,
    preflight_routes,
)
from core.cost_metering import open_cost_recorder
from core.cost_receipts import (
    BUCKET_GRADING,
    STATUS_COMPLETE,
    CostReceipt,
    CostReceiptLedger,
    ledger_reference,
    summarise_receipts,
)
from core.cost_projection import repo_relative_ledger_path
from core.experiment_config import ExperimentConfig
from core.grader import (
    Grader,
    GradingDeadlineExceeded,
    _is_critical_item,
    grader_transport_options,
    resolve_tool_prompt_path,
)
from core.grade_payload import canonical_rate, validate_grade_payload
from core.task_checkpoint import (
    CheckpointRejected,
    build_progress,
    discard_checkpoint,
    load_checkpoint,
    write_checkpoint,
)
from core.inference_manifest import (
    GOLD_PROVENANCE_STATUS,
    canonical_task_id,
    canonicalize_inference_payload,
    task_deliverable_dir,
    validate_local_deliverables,
)
from core.public_error import public_provider_error_text
from core.rubric_loader import RubricLoader
from core.tool_calling_judge import resolve_visual_file_cap
from core.tools import ReadDeliverableError, get_renderer_fingerprint

SCHEMA_VERSION = "1.4"
GRADED_BY_VERSION = "0.1.0"
FULL_HF_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
FULL_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
#: How many times one identical run may be repeated. A variance measurement
#: needs a handful of repeats, not an open-ended budget, and every repeat past
#: the first is a second full charge for a corpus that has already been graded.
MAX_RUN_ORDINAL = 10


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ordered_task_ids_sha256(task_ids: list[str]) -> str:
    encoded = json.dumps(
        task_ids,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def hash_config(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def _batch_runner_root() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "step8_grade.py").is_file():
        return cwd
    nested = cwd / "batch-runner"
    if (nested / "step8_grade.py").is_file():
        return nested.resolve()
    return cwd


def _checked_grader_source_file(batch_root: Path, path: Path) -> tuple[str, Path]:
    candidate = path if path.is_absolute() else batch_root / path
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(batch_root)
    except ValueError as exc:
        raise ValueError(f"grader source path is outside batch-runner: {path}") from exc

    current = batch_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"grader source path must not be a symlink: {relative}")
    if not candidate.is_file():
        raise ValueError(f"grader source file is missing: {relative}")
    if candidate.resolve() != candidate:
        raise ValueError(f"grader source path must not traverse a symlink: {relative}")
    return f"batch-runner/{relative.as_posix()}", candidate


def _checked_repository_config_file(
    batch_root: Path, path: Path
) -> tuple[str, Path]:
    repo_root = batch_root.parent
    candidate = path if path.is_absolute() else batch_root / path
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(
            f"grading config path is outside the repository: {path}"
        ) from exc

    current = repo_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(
                f"grading config path must not be a symlink: {relative}"
            )
    if not candidate.is_file():
        raise ValueError(f"grading config file is missing: {relative}")
    if candidate.resolve() != candidate:
        raise ValueError(
            f"grading config path must not traverse a symlink: {relative}"
        )
    return relative.as_posix(), candidate


def compute_grader_source_hash(config_path: str | Path, config: dict) -> str:
    batch_root = _batch_runner_root()
    core_root = batch_root / "core"
    if core_root.is_symlink() or not core_root.is_dir():
        raise ValueError("grader source directory is missing or symlinked: core")

    core_python_files: list[Path] = []
    for candidate in core_root.rglob("*"):
        if candidate.is_symlink():
            raise ValueError(
                f"grader source path must not be a symlink: {candidate.relative_to(batch_root)}"
            )
        if candidate.is_file() and candidate.suffix == ".py":
            core_python_files.append(candidate)
    if not core_python_files:
        raise ValueError("grader source directory contains no Python files: core")

    source_paths = [
        batch_root / "step8_grade.py",
        *core_python_files,
        batch_root / "schemas" / "grade.schema.json",
        batch_root / "requirements.txt",
        batch_root / "scripts" / "download_inference_from_hf.py",
        Path(config["prompt"]["template"]),
    ]
    if config.get("prompt", {}).get("tool_template") or (
        (config.get("judge") or {}).get("tools", {}).get("read_deliverable")
    ):
        source_paths.append(resolve_tool_prompt_path(config))

    checked: dict[str, Path] = {}
    for source_path in source_paths:
        relative, candidate = _checked_grader_source_file(batch_root, source_path)
        if relative in checked:
            raise ValueError(f"duplicate grader source path: {relative}")
        checked[relative] = candidate
    config_relative, config_candidate = _checked_repository_config_file(
        batch_root, Path(config_path)
    )
    if config_relative in checked:
        raise ValueError(f"duplicate grader source path: {config_relative}")
    checked[config_relative] = config_candidate

    digest = hashlib.sha256()
    digest.update(b"gdpval-grader-source-v1\x00")
    for relative, candidate in sorted(checked.items()):
        relative_bytes = relative.encode("utf-8")
        content = candidate.read_bytes()
        digest.update(len(relative_bytes).to_bytes(8, "big"))
        digest.update(relative_bytes)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


#: Suffix that separates a repeat's ledger namespace from run 1's. Exported so
#: the tests that read committed ledgers can tell a pre-fix repeat from one
#: minted after this rule existed, without hard-coding the spelling twice.
REPEAT_RUN_ID_SUFFIX = "|run"


def make_cost_run_id(
    *,
    experiment_yaml_name: str,
    config_hash: str,
    grader_source_hash: str,
    run_ordinal: int = 1,
) -> str:
    """Name the run that a cost ledger's call identifiers hang off.

    The first three parts are the run's scientific identity: same inference, same
    grading config, same grader source. A repeat run exists precisely to hold all
    three fixed, so on its own that identity cannot separate repeat 2 from repeat
    1 -- by construction it is the same string.

    That is fine for everything except the ledger. Call identifiers are derived
    from *where* a call sits in its run and never from what it says
    (``core.cost_receipts.make_call_id`` hashes run, task, stage, retry kind,
    attempt and sequence), so with an identical run id repeat 2's first call on a
    task is named exactly what repeat 1's was. They are not the same call:
    different request body, different tokens, separately billed.
    ``CostReceiptLedger`` keys on ``call_id``, and ``import_jsonl`` updates a row
    it already holds rather than inserting one, so the later repeat silently
    overwrites the earlier and its calls leave every total counted by identifier.

    ``core.cost_metering`` already folds its round counter into the same identity
    one level down, for the same reason. This is that, one level up.

    Only past run 1, so the canonical run keeps the identifiers already published
    beside it and no committed ledger is renamed by this change.
    """
    if run_ordinal < 1:
        raise ValueError(f"run_ordinal must be at least 1: {run_ordinal}")
    run_id = f"{experiment_yaml_name}|{config_hash}|{grader_source_hash}"
    if run_ordinal > 1:
        run_id = f"{run_id}{REPEAT_RUN_ID_SUFFIX}{run_ordinal}"
    return run_id


def _config_name_slug(config_name: Any) -> str:
    if not isinstance(config_name, str) or not config_name.strip():
        raise ValueError("config_name must be a non-empty string")
    if any(char in config_name for char in ("\r", "\n", "/", "\\")):
        raise ValueError("config_name must not contain newlines or path separators")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", config_name.strip())
    slug = slug.strip("._-")
    if not slug:
        raise ValueError("config_name has no filesystem-safe characters")
    return slug


# One directory, because experiments are kept in one: the run-place comparison
# holds its three configs in `experiments/execution_envelope/`. Each part has to
# open with a letter or a digit, so a leading dot, a leading dash and a leading
# separator are all refused, and '..' cannot be written at all.
_EXPERIMENT_NAME_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}(?:/[A-Za-z0-9][A-Za-z0-9._-]{0,99})?"
)

# What the separator becomes where the name has to be one component.
EXPERIMENT_PATH_SEPARATOR_SLUG = "__"


def _experiment_path_slug(experiment_id: Any) -> str:
    """The experiment's name, as a single filesystem component.

    An experiment may be grouped into a directory, so the name arriving here
    can carry a separator -- while a grade filename, the shard directory under
    it and the GitHub artifact the workflow uploads must each be one component.
    The separator becomes ``__``.

    That flattening is only safe while it is injective, and it is injective
    only while no name carries ``__`` of its own: were one to, it could land on
    a neighbour's grade file, and `grade-run.yml` inherits a paid approval by
    matching this stem, so two names collapsing onto one stem would hand one
    experiment's approval to another. A name containing ``__`` is therefore
    refused rather than flattened. `grade-run.yml` refuses the same names at
    dispatch; this is the half that holds when step 8 is run directly.

    Surrounding whitespace is refused rather than trimmed. `load_experiment_yaml`
    opens the name as given, so trimming here would validate one name and open
    another.
    """
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise ValueError("experiment name must be a non-empty string")
    name = experiment_id
    if EXPERIMENT_PATH_SEPARATOR_SLUG in name:
        raise ValueError(
            f"experiment name must not contain {EXPERIMENT_PATH_SEPARATOR_SLUG!r}: "
            "it is what a directory separator becomes, and two names must not "
            f"flatten onto one file (got {name!r})"
        )
    if not _EXPERIMENT_NAME_RE.fullmatch(name) or name.endswith(
        (".", ".lock", ".yaml", ".yml")
    ):
        raise ValueError(
            "experiment name must be one path part, or two separated by '/', "
            "each opening with a letter or a digit and made of letters, "
            "digits, '.', '_' and '-', and must not bring the '.yaml' this "
            f"step adds (got {name!r})"
        )
    return name.replace("/", EXPERIMENT_PATH_SEPARATOR_SLUG)


def resolve_grade_output_path(
    config: dict,
    *,
    experiment_id: str,
    judge_slug: str,
    config_hash: str,
    rubric_sha: str,
    rubric_short_sha: str,
    prompt_version: str,
    inference_sha: str | None = None,
    grader_source_hash: str | None = None,
    diagnostic_task_scope_sha: str | None = None,
    shard_index: int = 0,
    shard_count: int = 1,
    run_ordinal: int = 1,
) -> Path:
    if not FULL_HF_SHA_RE.fullmatch(rubric_sha):
        raise ValueError(
            "rubric_sha must be a full 40-character lowercase HF commit SHA"
        )
    if not isinstance(inference_sha, str) or not FULL_HF_SHA_RE.fullmatch(
        inference_sha
    ):
        raise ValueError(
            "inference_sha must be a full 40-character lowercase HF commit SHA"
        )
    if not isinstance(grader_source_hash, str) or not FULL_SHA256_RE.fullmatch(
        grader_source_hash
    ):
        raise ValueError(
            "grader_source_hash must be a full 64-character lowercase SHA-256"
        )
    if (
        diagnostic_task_scope_sha is not None
        and not FULL_SHA256_RE.fullmatch(diagnostic_task_scope_sha)
    ):
        raise ValueError(
            "diagnostic_task_scope_sha must be a full lowercase SHA-256"
        )
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError(
            "shard_index must satisfy 0 <= index < shard_count (count >= 1)"
        )
    if not 1 <= run_ordinal <= MAX_RUN_ORDINAL:
        raise ValueError(
            f"run_ordinal must satisfy 1 <= ordinal <= {MAX_RUN_ORDINAL}"
        )
    out_name = config["output"]["filename_template"].format(
        exp_id=_experiment_path_slug(experiment_id),
        judge_slug=judge_slug,
        config_name=_config_name_slug(config.get("config_name")),
        config_hash=config_hash,
        rubric_sha=rubric_sha,
        rubric_short_sha=rubric_short_sha,
        prompt_v=prompt_version,
        inference_sha=inference_sha or "",
        inference_short_sha=(inference_sha or "")[:7],
        grader_source_hash=grader_source_hash or "",
        grader_source_hash_short=(grader_source_hash or "")[:16],
    )
    if any(char in out_name for char in ("\r", "\n")) or Path(out_name).name != out_name:
        raise ValueError("formatted grade filename must be a single safe path component")
    output_root = Path(config["output"]["directory"])
    if diagnostic_task_scope_sha is not None:
        output_root = output_root / "_diagnostic" / diagnostic_task_scope_sha
    if run_ordinal > 1:
        # Measuring how far a score drifts between reruns needs the SAME grader
        # source, config, corpus and inputs graded more than once. Nothing that
        # identifies the run may change, so every repeat resolves to one path,
        # where the second would be refused as already existing and --force
        # would erase the first.
        #
        # Fork above the shard fork, not below it, so the two compose: a repeat
        # that is too large for one four-hour chunk still shards, and its shards
        # land under this repeat's own root instead of mixing with run 1's. Run
        # 1 keeps the canonical path, so the original of a repeat set stays an
        # ordinary run. `scripts/aggregate-grades.mjs` globs `data/grades/*.json`
        # without descending, so a repeat is never published to the dashboard as
        # a second, competing result for the same config -- the repeats exist to
        # be compared with each other, not to replace the run they repeat.
        output_root = output_root / "_repeats" / f"run-{run_ordinal:03d}"
    if shard_count > 1:
        # Every shard of a run resolves to the same `out_name`, because their
        # identity inputs (config_hash, rubric_sha, grader_source_hash, ...) are
        # identical by construction — that sameness is the whole point, it is
        # what lets step9 prove the shards belong together. So the *path* has to
        # fork or N concurrent jobs would write and commit the same file.
        #
        # Fork it exactly the way `_diagnostic/<scope_sha>/` already does: below
        # the canonical name, never inside it. No identity input is touched, so
        # the cache key is unchanged and each shard's path is stable across its
        # own rc=7 resume chunks. The `_shards/` directory also keeps these
        # partials out of `scripts/aggregate-grades.mjs`, which globs
        # `data/grades/*.json` non-recursively and would otherwise publish an
        # unfinished slice to the dashboard as if it were a graded run.
        return (
            output_root
            / "_shards"
            / Path(out_name).stem
            / f"shard-{shard_index:03d}-of-{shard_count:03d}.json"
        )
    return output_root / out_name


def _repo_relative_grade_file(out_path: Path) -> str:
    cwd = Path.cwd().resolve()
    repo_root = cwd.parent if cwd.name == "batch-runner" else cwd
    try:
        relative = out_path.resolve().relative_to(repo_root)
    except ValueError as exc:
        raise ValueError("grade output path must remain inside the repository") from exc
    value = relative.as_posix()
    if not value or any(char in value for char in ("\r", "\n")):
        raise ValueError("grade output path is not safe for GITHUB_OUTPUT")
    return value


def _repo_root() -> Path:
    """The root a published ledger pointer is relative to.

    Derived exactly as ``_repo_relative_grade_file`` derives it, and kept
    beside it so the two cannot drift: a pointer written against one root and
    read against another is the defect this is here to close, not a new way to
    reintroduce it.
    """
    cwd = Path.cwd().resolve()
    return cwd.parent if cwd.name == "batch-runner" else cwd


def _exit_on_signal(signum: int, _frame: Any) -> None:
    """Leave through ``SystemExit`` so the exit handlers get to run.

    GitHub sends SIGTERM when a job passes its ``timeout-minutes``. Python's
    default disposition for it kills the process where it stands, which skips
    ``atexit`` — and the cost ledger's final export is an ``atexit`` handler,
    because a run that is being killed is precisely the run that never reached
    a save. Raising ``SystemExit`` instead unwinds normally and lets the export
    happen. The code is the conventional ``128 + signal`` so that nothing
    downstream can read a cancellation as a clean finish.
    """
    print(
        f"[signal] received {signum}; unwinding so exit handlers can run",
        file=sys.stderr,
    )
    sys.exit(128 + signum)


def _write_github_output(name: str, value: str) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("invalid GitHub output name")
    if any(char in value for char in ("\r", "\n")):
        raise ValueError("GitHub output value must be a single line")
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run rubric-based grading for one experiment")
    parser.add_argument("experiment_yaml_name", help="Experiment YAML name without .yaml")
    parser.add_argument("--config", required=True, help="Grading config path")
    parser.add_argument("--force", action="store_true", help="Overwrite if cache-key output exists")
    parser.add_argument("--dry-run", action="store_true", help="Only classify precheck vs judge")
    parser.add_argument("--tasks", help="Comma-separated task ids")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks")
    parser.add_argument("--source", choices=["local", "hf"], default="local")
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Resume an in-progress grade run. Reads any existing grade JSON at "
            "the templated output path, skips tasks whose task_id is already "
            "graded, and continues. Combined with the time guard (env "
            "GRADER_TIME_BUDGET_SEC, default 14400 = 4h), this lets a long "
            "grade run chunk itself across multiple GH Actions invocations. "
            "Exit code 7 is returned when the time budget is hit BEFORE "
            "completing all tasks; the caller (workflow) should re-invoke "
            "with --resume to continue from the partial."
        ),
    )
    parser.add_argument(
        "--shard-count",
        type=int,
        default=1,
        help=(
            "Split the run across N workers. Each shard grades a stride slice "
            "(tasks[i::N]) of the SAME canonical task order, so the corpus "
            "identity fields (expected_task_count, "
            "expected_ordered_task_ids_sha256) still describe the full corpus "
            "and every shard resolves to the same cache key. A shard emits "
            "run_status 'partial'; step9_merge_shards.py reassembles the "
            "shards into the final payload. Default 1 = serial, unsharded. "
            "Sharding is NOT a diagnostic selection: it changes who grades "
            "what, not which tasks are in scope."
        ),
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=0,
        help="0-based index of this shard; must satisfy 0 <= index < count.",
    )
    parser.add_argument(
        "--run-ordinal",
        type=int,
        default=1,
        help=(
            "Which repeat of an otherwise identical run this is. Measuring how "
            "much a score moves between reruns needs the SAME grader source, "
            "config, corpus and inputs graded more than once, so nothing that "
            "identifies the run may change -- which leaves every repeat "
            "resolving to one output path, where the second would be refused "
            "as already existing and --force would erase the first. Ordinals "
            "above 1 fork the output directory the way --shard-count forks the "
            "filename, above the shard fork so a repeat too large for one "
            "chunk can still shard, and touch no identity input. Default 1 "
            "keeps the canonical path, so run 1 of a repeat set is an ordinary "
            "run and needs no flag."
        ),
    )
    parser.add_argument(
        "--source-experiment-id",
        default=None,
        help=(
            "Phase 2 source linkage: experiment_id of the inference run that "
            "produced the deliverables being graded. Defaults to "
            "experiment_yaml_name. Useful when the grade exp name diverges "
            "from the inference run directory (e.g. re-grading a renamed run)."
        ),
    )
    args = parser.parse_args()
    if args.shard_count < 1:
        parser.error("--shard-count must be >= 1")
    if not 0 <= args.shard_index < args.shard_count:
        parser.error(
            "--shard-index must satisfy 0 <= index < --shard-count "
            f"(got index={args.shard_index}, count={args.shard_count})"
        )
    if not 1 <= args.run_ordinal <= MAX_RUN_ORDINAL:
        parser.error(
            f"--run-ordinal must satisfy 1 <= ordinal <= {MAX_RUN_ORDINAL} "
            f"(got {args.run_ordinal})"
        )
    return args


def validate_grading_config(config: dict) -> None:
    # PR2 task 208 — accept both schema 1.0 (legacy v1, text-extract path)
    # and 2.0 (v2 tool-calling path). The validator branches on the
    # presence of judge.tools.read_deliverable, not on the literal
    # version string, so user-authored v1 configs that forget to bump
    # schema_version still validate correctly.
    schema_version = config.get("schema_version")
    if schema_version not in ("1.0", "2.0"):
        raise ValueError("grading config schema_version must be '1.0' or '2.0'")

    required = [
        "schema_version",
        "config_name",
        "judge",
        "rubric",
        "prompt",
        "output",
    ]
    for key in required:
        if key not in config:
            raise ValueError(f"missing config key: {key}")

    judge = config.get("judge", {})
    for key in ["provider", "api", "model", "deployment"]:
        if key not in judge:
            raise ValueError(f"missing config key: judge.{key}")
    if "endpoint_env" in judge:
        raise ValueError(
            "judge.endpoint_env is deprecated; use typed Azure AI runtime env"
        )
    if judge["model"] != judge["deployment"]:
        raise ValueError("judge.model and judge.deployment must match")
    allowed_reasoning_efforts = {
        "none", "low", "medium", "high", "xhigh", "max"
    }
    reasoning = judge.get("reasoning", {})
    if not isinstance(reasoning, dict):
        raise ValueError("judge.reasoning must be an object")
    if (
        "effort" in reasoning
        and reasoning["effort"] not in allowed_reasoning_efforts
    ):
        raise ValueError("judge.reasoning.effort is invalid")
    generation = judge.get("generation", {})
    if not isinstance(generation, dict):
        raise ValueError("judge.generation must be an object")
    if (
        "finalization_reasoning_effort" in generation
        and generation["finalization_reasoning_effort"]
        not in allowed_reasoning_efforts
    ):
        raise ValueError(
            "judge.generation.finalization_reasoning_effort is invalid"
        )
    grader_route_workloads(config)

    # --- v2 tool-calling block (optional) ------------------------------
    tools = (judge.get("tools") or {})
    if tools:
        rd = tools.get("read_deliverable")
        if rd is None:
            raise ValueError(
                "judge.tools present but missing read_deliverable block"
            )
        ops = rd.get("ops")
        if not isinstance(ops, list) or not ops:
            raise ValueError(
                "judge.tools.read_deliverable.ops must be a non-empty list"
            )
        allowed_ops = {"inspect_structure", "read_content",
                       "inspect_formatting", "probe_audio", "probe_video"}
        if "render_to_image" in ops:
            raise ValueError(
                "judge.tools.read_deliverable.ops must not expose "
                "render_to_image; visual rendering is harness-owned"
            )
        bad = [op for op in ops if op not in allowed_ops]
        if bad:
            raise ValueError(
                f"judge.tools.read_deliverable.ops contains unknown ops: {bad}"
            )

    # --- v2 perception block (optional) --------------------------------
    perception = judge.get("perception", {})
    if not isinstance(perception, dict):
        raise ValueError("judge.perception must be an object")
    if perception:
        for sub in ("visual", "audio"):
            sub_cfg = perception.get(sub)
            if sub_cfg is None:
                continue
            if not isinstance(sub_cfg, dict):
                raise ValueError(
                    f"judge.perception.{sub} must be an object"
                )
            if not any(key in sub_cfg for key in ("model", "deployment")):
                raise ValueError(
                    f"judge.perception.{sub} present but missing model/deployment"
                )
        visual = perception.get("visual")
        if (
            isinstance(visual, dict)
            and "reasoning_effort" in visual
            and visual["reasoning_effort"] not in allowed_reasoning_efforts
        ):
            raise ValueError(
                "judge.perception.visual.reasoning_effort is invalid"
            )
        # resolve_visual_file_cap raises on anything that is not a positive
        # integer. Calling it here turns a bad cap into a config error before
        # dispatch rather than a judge_error partway through a paid shard.
        resolve_visual_file_cap(judge)

    # --- v2 critical block (optional) ----------------------------------
    critical = (judge.get("critical") or {})
    if critical:
        rule = critical.get("rule")
        if rule not in (None, "abs_max_score_threshold"):
            raise ValueError(
                f"judge.critical.rule unknown: {rule!r}; "
                "expected 'abs_max_score_threshold'"
            )

    rubric = config.get("rubric", {})
    for key in ["repo_id", "revision", "cache_dir"]:
        if key not in rubric:
            raise ValueError(f"missing config key: rubric.{key}")

    prompt = config.get("prompt", {})
    if "template" not in prompt or "version" not in prompt:
        raise ValueError("missing config key: prompt.template/prompt.version")
    if not Path(prompt["template"]).exists():
        raise ValueError(f"prompt template not found: {prompt['template']}")
    # v2 configs MAY also set prompt.tool_template; if set, must exist.
    if "tool_template" in prompt and not Path(prompt["tool_template"]).exists():
        raise ValueError(
            f"prompt.tool_template not found: {prompt['tool_template']}"
        )

    output = config.get("output", {})
    if "directory" not in output or "filename_template" not in output:
        raise ValueError("missing config key: output.directory/output.filename_template")

    repo_id = str(rubric.get("repo_id", ""))
    if "/" not in repo_id:
        raise ValueError("rubric.repo_id must be owner/name format")

    if int(config.get("tpm_guard", {}).get("max_concurrent", 1)) < 1:
        raise ValueError("tpm_guard.max_concurrent must be >= 1")

    rerun_identity = config.get("rerun_identity")
    if rerun_identity is not None:
        if schema_version != "2.0" or not isinstance(rerun_identity, dict):
            raise ValueError("rerun_identity requires a schema 2.0 object")
        required_identity_fields = {
            "experiment_id",
            "expected_task_count",
            "rubric_commit_sha",
            "inference_revision",
        }
        allowed_identity_fields = required_identity_fields | {
            "task_ids",
            "allow_legacy_missing_provenance",
        }
        identity_fields = set(rerun_identity)
        if (
            not required_identity_fields.issubset(identity_fields)
            or not identity_fields.issubset(allowed_identity_fields)
        ):
            raise ValueError(
                "rerun_identity must contain experiment_id, "
                "expected_task_count, rubric_commit_sha, and inference_revision; "
                "task_ids and allow_legacy_missing_provenance are optional"
            )
        experiment_id = rerun_identity["experiment_id"]
        if not isinstance(experiment_id, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", experiment_id
        ):
            raise ValueError("rerun_identity.experiment_id is invalid")
        expected_task_count = rerun_identity["expected_task_count"]
        if (
            type(expected_task_count) is not int
            or expected_task_count < 1
            or expected_task_count > 220
        ):
            raise ValueError("rerun_identity.expected_task_count is invalid")
        for field_name in ("rubric_commit_sha", "inference_revision"):
            value = rerun_identity[field_name]
            if not isinstance(value, str) or not FULL_HF_SHA_RE.fullmatch(value):
                raise ValueError(f"rerun_identity.{field_name} is invalid")
        if rubric["revision"] != rerun_identity["rubric_commit_sha"]:
            raise ValueError(
                "rubric.revision must match rerun_identity.rubric_commit_sha"
            )
        task_ids = rerun_identity.get("task_ids")
        if task_ids is not None:
            if not isinstance(task_ids, list) or not task_ids:
                raise ValueError("rerun_identity.task_ids must be a non-empty list")
            if any(
                not isinstance(task_id, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", task_id)
                for task_id in task_ids
            ):
                raise ValueError("rerun_identity.task_ids contains an invalid task ID")
            if len(task_ids) != len(set(task_ids)):
                raise ValueError("rerun_identity.task_ids contains duplicate task IDs")
            if len(task_ids) != expected_task_count:
                raise ValueError(
                    "rerun_identity.task_ids count must match expected_task_count"
                )
        allow_legacy_provenance = rerun_identity.get(
            "allow_legacy_missing_provenance"
        )
        if (
            allow_legacy_provenance is not None
            and type(allow_legacy_provenance) is not bool
        ):
            raise ValueError(
                "rerun_identity.allow_legacy_missing_provenance must be boolean"
            )
        if allow_legacy_provenance is True and not task_ids:
            raise ValueError(
                "rerun_identity.allow_legacy_missing_provenance requires "
                "pinned task_ids"
            )

    anchor_projection = config.get("anchor_projection")
    if anchor_projection is not None:
        if not isinstance(anchor_projection, dict):
            raise ValueError("anchor_projection must be an object")
        if not isinstance(rerun_identity, dict) or not rerun_identity.get("task_ids"):
            raise ValueError("anchor_projection requires pinned rerun task_ids")
        required_projection_fields = {
            "method",
            "anchor_config_name",
            "anchor_task_count",
            "anchor_ordered_task_ids_sha256",
            "anchor_source_inference_repo_id",
            "baseline_payload_sha256",
            "baseline_schema_version",
            "baseline_perception_wired",
            "baseline_main_calls",
            "baseline_main_latency_ms",
            "baseline_final_json_parse_failed",
            "baseline_empty_final_text",
            "anchor_visual_criteria",
            "anchor_audio_criteria",
            "full_task_count",
            "full_visual_criteria",
            "full_audio_criteria",
            "chunk_envelope_hours",
        }
        if set(anchor_projection) != required_projection_fields:
            raise ValueError(
                "anchor_projection fields must match the versioned contract"
            )
        if anchor_projection["method"] != "modality_normalized_v1":
            raise ValueError("anchor_projection.method is invalid")
        if anchor_projection["anchor_config_name"] != config["config_name"]:
            raise ValueError(
                "anchor_projection config name must match config_name"
            )
        if not FULL_SHA256_RE.fullmatch(
            str(anchor_projection["anchor_ordered_task_ids_sha256"])
        ):
            raise ValueError("anchor_projection task identity SHA is invalid")
        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*",
            str(anchor_projection["anchor_source_inference_repo_id"]),
        ):
            raise ValueError(
                "anchor_projection source inference repo is invalid"
            )
        experiment_path = (
            _batch_runner_root()
            / "experiments"
            / f"{rerun_identity['experiment_id']}.yaml"
        )
        try:
            experiment = yaml.safe_load(
                experiment_path.read_text(encoding="utf-8")
            )
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(
                "anchor_projection experiment source is unavailable"
            ) from exc
        experiment_source = str(
            (experiment or {}).get("data", {}).get("source", "")
        ).strip()
        if (
            anchor_projection["anchor_source_inference_repo_id"]
            != experiment_source
        ):
            raise ValueError(
                "anchor_projection source repo must match experiment source"
            )
        if not FULL_SHA256_RE.fullmatch(
            str(anchor_projection["baseline_payload_sha256"])
        ):
            raise ValueError("anchor_projection baseline payload SHA is invalid")
        if anchor_projection["baseline_schema_version"] != "1.0":
            raise ValueError("anchor_projection baseline schema must be 1.0")
        if anchor_projection["baseline_perception_wired"] is not False:
            raise ValueError(
                "anchor_projection baseline perception must remain unwired"
            )
        positive_integer_fields = (
            "anchor_task_count",
            "baseline_main_calls",
            "baseline_final_json_parse_failed",
            "baseline_empty_final_text",
            "anchor_visual_criteria",
            "anchor_audio_criteria",
            "full_task_count",
            "full_visual_criteria",
            "full_audio_criteria",
            "chunk_envelope_hours",
        )
        if any(
            type(anchor_projection[field_name]) is not int
            or anchor_projection[field_name] <= 0
            for field_name in positive_integer_fields
        ):
            raise ValueError(
                "anchor_projection count and envelope fields must be positive integers"
            )
        baseline_latency = anchor_projection["baseline_main_latency_ms"]
        if (
            not isinstance(baseline_latency, (int, float))
            or not math.isfinite(baseline_latency)
            or baseline_latency <= 0
        ):
            raise ValueError(
                "anchor_projection baseline main latency must be positive"
            )
        if anchor_projection["full_task_count"] < len(
            rerun_identity["task_ids"]
        ):
            raise ValueError(
                "anchor_projection full task count is smaller than anchor"
            )
        if anchor_projection["anchor_task_count"] != len(
            rerun_identity["task_ids"]
        ):
            raise ValueError(
                "anchor_projection task count must match pinned task_ids"
            )
        if anchor_projection["anchor_ordered_task_ids_sha256"] != (
            _ordered_task_ids_sha256(rerun_identity["task_ids"])
        ):
            raise ValueError(
                "anchor_projection task identity must match pinned task_ids"
            )


def requires_track2_office_renderer(config: dict) -> bool:
    if config.get("schema_version") != "2.0":
        return False
    judge = config.get("judge")
    if not isinstance(judge, dict):
        return False
    tools = judge.get("tools")
    read_tool = tools.get("read_deliverable") if isinstance(tools, dict) else None
    perception = judge.get("perception")
    visual = perception.get("visual") if isinstance(perception, dict) else None
    visual_deployment = (
        canonical_deployment(visual, "judge.perception.visual")
        if isinstance(visual, dict)
        else None
    )
    return (
        isinstance(read_tool, dict)
        and isinstance(read_tool.get("ops"), list)
        and bool(read_tool["ops"])
        and isinstance(visual, dict)
        and bool(visual_deployment)
    )


def source_inference_repo_id(inference_results: dict, schema_version: str) -> str | None:
    value = inference_results.get("source_repo_id")
    if value is None and schema_version != "2.0":
        value = inference_results.get("source")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def source_inference_revision(inference_results: dict) -> str | None:
    value = inference_results.get("source_revision")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def resolve_source_inference_identity(
    inference_results: dict, schema_version: str
) -> tuple[str | None, str | None]:
    repo_id = source_inference_repo_id(inference_results, schema_version)
    revision = source_inference_revision(inference_results)
    if schema_version == "2.0":
        if repo_id is None or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*",
            repo_id,
        ):
            raise ValueError(
                "Track 2 source_repo_id must be a canonical owner/name"
            )
        if revision is None or not FULL_HF_SHA_RE.fullmatch(revision):
            raise ValueError(
                "Track 2 source_revision must be a full 40-character lowercase HF commit SHA"
            )
    return repo_id, revision


def _validate_grade_resume_identity(
    existing: dict,
    *,
    experiment_id: str,
    rubric_commit_sha: str,
    prompt_version: str,
    config_hash: str,
    source_inference_repo_id: str,
    source_inference_revision: str,
    grader_source_hash: str,
    renderer_fingerprint: dict[str, str] | None,
    anchor_projection: dict | None,
) -> None:
    checks = (
        ("schema_version", existing.get("schema_version"), SCHEMA_VERSION),
        ("experiment_id", existing.get("experiment_id"), experiment_id),
        (
            "rubric.commit_sha",
            (existing.get("rubric") or {}).get("commit_sha")
            if isinstance(existing.get("rubric"), dict) else None,
            rubric_commit_sha,
        ),
        (
            "prompt.version",
            (existing.get("prompt") or {}).get("version")
            if isinstance(existing.get("prompt"), dict) else None,
            prompt_version,
        ),
        (
            "judge.config_hash",
            (existing.get("judge") or {}).get("config_hash")
            if isinstance(existing.get("judge"), dict) else None,
            config_hash,
        ),
        (
            "source_inference_repo_id",
            existing.get("source_inference_repo_id"),
            source_inference_repo_id,
        ),
        (
            "source_inference_revision",
            existing.get("source_inference_revision"),
            source_inference_revision,
        ),
        (
            "grader_source_hash",
            existing.get("grader_source_hash"),
            grader_source_hash,
        ),
        (
            "anchor_projection",
            existing.get("anchor_projection"),
            anchor_projection,
        ),
    )
    if renderer_fingerprint is not None:
        checks += ((
            "renderer_fingerprint",
            existing.get("renderer_fingerprint"),
            renderer_fingerprint,
        ),)
    for field_name, actual, expected in checks:
        if actual != expected:
            state = "missing" if actual is None else "mismatch"
            raise ValueError(
                f"Grade resume identity {state} for {field_name}: "
                f"existing={actual!r}, current={expected!r}"
            )


def _validate_pinned_rerun_identity(
    config: dict,
    *,
    experiment_id: str,
    task_ids: list[str] | None = None,
    task_count: int | None = None,
    rubric_commit_sha: str,
    inference_revision: str | None,
) -> None:
    identity = config.get("rerun_identity")
    if identity is None:
        return
    actual_task_count = len(task_ids) if task_ids is not None else task_count
    checks = (
        ("experiment_id", experiment_id, identity["experiment_id"]),
        ("task_count", actual_task_count, identity["expected_task_count"]),
        (
            "rubric_commit_sha",
            rubric_commit_sha,
            identity["rubric_commit_sha"],
        ),
        (
            "inference_revision",
            inference_revision,
            identity["inference_revision"],
        ),
    )
    for field_name, actual, expected in checks:
        if actual != expected:
            raise ValueError(
                f"pinned rerun identity mismatch for {field_name}: "
                f"actual={actual!r}, expected={expected!r}"
            )
    expected_task_ids = identity.get("task_ids")
    if expected_task_ids is not None and task_ids != expected_task_ids:
        raise ValueError(
            "pinned rerun identity mismatch for task_ids: "
            f"actual={task_ids!r}, expected={expected_task_ids!r}"
        )


def _validate_azure_ai_resume_identity(
    existing: dict,
    azure_ai_routes: list[dict[str, str]],
    primary_runtime_fingerprint: str,
) -> None:
    actual = existing.get("azure_ai_routes")
    if actual != azure_ai_routes:
        state = "missing" if actual is None else "mismatch"
        raise ValueError(
            "Azure AI resume identity "
            f"{state} for azure_ai_routes: existing={actual!r}, "
            f"current={azure_ai_routes!r}"
        )
    actual_fingerprint = existing.get("azure_ai_runtime_fingerprint")
    if actual_fingerprint != primary_runtime_fingerprint:
        state = "missing" if actual_fingerprint is None else "mismatch"
        raise ValueError(
            "Azure AI resume identity "
            f"{state} for azure_ai_runtime_fingerprint: "
            f"existing={actual_fingerprint!r}, "
            f"current={primary_runtime_fingerprint!r}"
        )


def _load_existing_grade(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            existing = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load existing grade JSON: {exc}") from exc
    if not isinstance(existing, dict):
        raise ValueError("top-level JSON must be an object")
    if not isinstance(existing.get("tasks"), list):
        raise ValueError("top-level tasks must be an array")
    return existing


def _task_ids(rows: list[dict], *, label: str) -> list[str]:
    task_ids: list[str] = []
    seen: set[str] = set()
    duplicates: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{label} task at index {index} must be an object")
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(
                f"{label} task at index {index} has no non-empty task_id"
            )
        if task_id in seen:
            duplicates.add(task_id)
        seen.add(task_id)
        task_ids.append(task_id)
    if duplicates:
        raise ValueError(
            f"{label} contains duplicate task_ids: {sorted(duplicates)}"
        )
    return task_ids


def _is_ordered_subsequence(candidate: list[str], universe: list[str]) -> bool:
    """True when ``candidate`` occurs inside ``universe`` in the same order.

    A serial ``--resume`` produces a prefix of the canonical order, but a shard
    (``--shard-count``) grades a stride slice, so its partial payload is an
    ordered *subsequence* instead. Every prefix is a subsequence, so accepting
    subsequences only widens what already validated.
    """
    remaining = iter(universe)
    return all(task_id in remaining for task_id in candidate)


def _shard_slice(
    tasks: list[dict], *, shard_index: int, shard_count: int
) -> list[dict]:
    """Return the stride slice of ``tasks`` this shard is responsible for.

    Stride (``tasks[i::n]``) rather than contiguous blocks: the corpus carries
    whatever ordering bias the source dataset had (sector runs, difficulty
    drift), and contiguous blocks would concentrate that bias into individual
    shards, making per-shard cost and wall-clock wildly uneven. A stride spreads
    it. The union of all shards is exactly ``tasks``, and each shard preserves
    the canonical relative order, so each partial payload is an ordered
    subsequence of the expected ids.
    """
    if shard_count <= 1:
        return list(tasks)
    return tasks[shard_index::shard_count]


def _validate_grade_task_set(
    existing: dict,
    expected_tasks: list[dict],
    *,
    require_complete: bool,
    complete_status: str = "final",
) -> set[str]:
    try:
        _validate_schema(existing)
    except (SchemaError, ValidationError) as exc:
        raise ValueError(
            f"existing grade schema validation failed: {exc.message}"
        ) from exc

    expected_ids = _task_ids(expected_tasks, label="current inference")
    existing_ids = _task_ids(existing["tasks"], label="existing grade")
    if complete_status not in {"final", "diagnostic"}:
        raise ValueError("complete grade status is invalid")
    expected_status = complete_status if require_complete else "partial"
    if existing.get("run_status") != expected_status:
        raise ValueError(
            f"existing grade run_status must be {expected_status!r}"
        )
    if existing.get("expected_task_count") != len(expected_ids):
        raise ValueError("existing grade expected task count mismatch")
    if existing.get("expected_ordered_task_ids_sha256") != (
        _ordered_task_ids_sha256(expected_ids)
    ):
        raise ValueError("existing grade expected task order mismatch")
    if require_complete:
        if existing_ids != expected_ids:
            raise ValueError("existing final grade task order is incomplete or mismatched")
    elif not _is_ordered_subsequence(existing_ids, expected_ids):
        raise ValueError(
            "existing partial grade tasks are not an ordered subsequence"
        )
    runtime_errors = [
        (task["task_id"], error)
        for task in existing["tasks"]
        if (error := _track2_task_runtime_error(task)) is not None
    ]
    if runtime_errors:
        raise ValueError(
            f"existing grade contains runtime failures: {runtime_errors}"
        )
    # A resumed chunk has to be able to load a payload whose cost total is
    # legitimately incomplete, because an earlier chunk may have graded a task
    # whose token counts never arrived. Those grades are still good; only the
    # bill is unknown. What is still refused is a payload that will not say
    # either way — the flag must be present and must be a boolean, so the fold
    # that produces the run's total can never be handed a missing or
    # truthy-ish value. `step9_merge_shards` demands exactly this of every
    # shard it merges.
    #
    # The rows are checked as well as the aggregate, and the rows are the ones
    # that matter: `_compute_summary` recomputes `summary.cost.usage_complete`
    # from these rows and never reads the aggregate loaded here, so a payload
    # that carries a tidy boolean at the top and silence underneath would sail
    # through a check on the aggregate alone. Refusing here rather than folding
    # the silence in costs nothing — this chunk has not graded anything yet —
    # and says which row is at fault instead of quietly marking the run's whole
    # cost total unknown for the rest of its life.
    aggregate_usage = existing["summary"]["cost"].get("usage_complete")
    if type(aggregate_usage) is not bool:
        raise ValueError(
            "existing grade aggregate usage flag is missing or not a boolean: "
            f"{aggregate_usage!r}"
        )
    silent_rows = [
        (task["task_id"], task.get("usage_complete"))
        for task in existing["tasks"]
        if type(task.get("usage_complete")) is not bool
    ]
    if silent_rows:
        raise ValueError(
            "existing grade task usage flag is missing or not a boolean: "
            f"{silent_rows}"
        )
    return set(existing_ids)


def load_experiment_yaml(experiment_yaml_name: str) -> ExperimentConfig:
    # Checked before the file is opened, not after. The name may carry one
    # directory -- `experiments/execution_envelope/` holds the run-place
    # comparison's configs -- and this is the only place it becomes a path, so
    # a name that could climb out of `experiments/` is refused here rather than
    # at the far end, where the grade filename is built. Same rule, one reading.
    _experiment_path_slug(experiment_yaml_name)
    path = Path("experiments") / f"{experiment_yaml_name}.yaml"
    return ExperimentConfig.from_yaml(str(path))


def load_local_inference_results() -> dict:
    path = Path("workspace") / "step2_inference_results.json"
    if not path.exists():
        raise FileNotFoundError(str(path))
    with open(path, "r", encoding="utf-8") as f:
        return canonicalize_inference_payload(json.load(f))


def filter_tasks(inference_results: dict, tasks_csv: str | None, limit: int) -> list[dict]:
    raw_tasks = inference_results.get("results")
    if not isinstance(raw_tasks, list):
        raise ValueError("inference results must contain a results array")
    source_ids = _task_ids(raw_tasks, label="inference results")
    if not source_ids:
        raise ValueError("inference results contain no tasks")
    if limit < 0:
        raise ValueError("--limit must be >= 0")

    tasks = list(raw_tasks)
    if tasks_csv is not None:
        requested = [part.strip() for part in tasks_csv.split(",") if part.strip()]
        if not requested:
            raise ValueError("--tasks must include at least one task_id")
        duplicate_requests = sorted({
            task_id for task_id in requested if requested.count(task_id) > 1
        })
        if duplicate_requests:
            raise ValueError(
                f"--tasks contains duplicate task_ids: {duplicate_requests}"
            )
        source_set = set(source_ids)
        missing = sorted(set(requested) - source_set)
        if missing:
            raise ValueError(f"--tasks requested unknown task_ids: {missing}")
        wanted = set(requested)
        tasks = [task for task in tasks if task["task_id"] in wanted]
    if limit > 0:
        tasks = tasks[:limit]
    return tasks


def filter_tasks_for_config(
    inference_results: dict,
    config: dict,
    *,
    tasks_csv: str | None,
    limit: int,
) -> tuple[list[dict], str | None]:
    """Resolve the graded task selection and classify how narrow it is.

    The second element is the pinned scope: ``None`` when the config pins
    nothing, ``"subset"`` when it pins a proper subset of the source corpus,
    and ``"complete"`` when the pinned list covers every task in it.

    Only ``"subset"`` is a *narrowed* scope. Pinning the whole corpus drops
    nothing — it asserts the corpus identity — so it is not a reason to fork
    the output into the diagnostic tree.
    """
    identity = config.get("rerun_identity")
    pinned_ids = identity.get("task_ids") if isinstance(identity, dict) else None
    if pinned_ids is None:
        return filter_tasks(inference_results, tasks_csv, limit), None

    pinned_tasks = filter_tasks(
        inference_results,
        ",".join(pinned_ids),
        0,
    )
    canonical_pinned_ids = [task["task_id"] for task in pinned_tasks]
    if canonical_pinned_ids != pinned_ids:
        raise ValueError(
            "config pinned task selection must follow canonical source order"
        )

    if tasks_csv is not None:
        cli_tasks = filter_tasks(inference_results, tasks_csv, 0)
        cli_ids = [task["task_id"] for task in cli_tasks]
        if cli_ids != canonical_pinned_ids:
            raise ValueError(
                "CLI --tasks conflicts with config pinned task selection"
            )

    if limit not in {0, len(canonical_pinned_ids)}:
        raise ValueError(
            "--limit conflicts with config pinned task selection: "
            f"expected 0 or {len(canonical_pinned_ids)}, got {limit}"
        )
    source_task_count = len(filter_tasks(inference_results, None, 0))
    # Canonical order was proven above, so equal counts mean the pinned list is
    # the source corpus rather than merely the same size as it.
    scope = "complete" if len(canonical_pinned_ids) == source_task_count else "subset"
    return pinned_tasks, scope


def _track2_task_runtime_error(task: dict) -> str | None:
    """Why this task's marks cannot be read, or ``None`` if they can.

    Everything named here leaves the *score* unreadable: a task that already
    carries a foreign error, items that are not a list, an item that is not an
    object, or a judge error left sitting inside the score it should have been
    excluded from. Any one of them stops the shard, because a number nobody
    can read is worse than no number at all.

    An incomplete token count is deliberately not on that list. It says
    nothing about whether the marking was right — only that what the marking
    cost is unknown. That is carried instead by the task's own
    ``usage_complete``, which the aggregate folds into
    ``summary.cost.usage_complete``, so the run still refuses to publish a
    cost figure it cannot stand behind while the grades it *can* stand behind
    survive.
    """
    existing_error = task.get("error")
    if existing_error and existing_error not in {
        "all_items_score_excluded",
        "no_deliverables",
        "selection_error",
    }:
        return str(existing_error)

    items = task.get("items")
    if not isinstance(items, list):
        return "invalid_items"
    for item in items:
        if not isinstance(item, dict):
            return "invalid_item"
        if (
            item.get("verdict") == "judge_error"
            and item.get("score_excluded") is not True
        ):
            return "invalid_score_exclusion"

    return None


def resolve_deliverable_dir(task_result: dict) -> str:
    task_id = canonical_task_id(task_result.get("task_id"))
    return str(Path(os.path.abspath(
        task_deliverable_dir(Path("workspace") / "upload", task_id)
    )))


def _judge_slug(model: str) -> str:
    return model.replace(".", "_")


def _read_schema() -> dict:
    path = Path("schemas") / "grade.schema.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    temp_identity = hashlib.sha256(os.fsencode(path.name)).hexdigest()[:16]
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".grade-{temp_identity}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _ci_pct(values: list[float]) -> float:
    if not values:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(var)
    return 1.96 * std / math.sqrt(n)


def _task_to_dict(
    task_grade,
    *,
    grading_wall_time_ms: float | None = None,
) -> dict:
    data = asdict(task_grade)
    if grading_wall_time_ms is not None:
        if not math.isfinite(grading_wall_time_ms) or grading_wall_time_ms < 0:
            raise ValueError("grading wall time must be finite and nonnegative")
        data["grading_wall_time_ms"] = round(grading_wall_time_ms, 2)
    data["graded_at"] = _now_iso()
    return data


def _unpriced_models(config: dict) -> list[str]:
    judge = config["judge"]
    models = [canonical_deployment(judge, "judge")]
    perception = judge.get("perception", {}) or {}
    for modality_name, modality in perception.items():
        if isinstance(modality, dict):
            models.append(canonical_deployment(
                modality,
                f"judge.perception.{modality_name}",
            ))
    return sorted(set(models))


#: Score buckets for ``summary.wow.score_density_histogram``. These labels are
#: a contract with ``bucketFromPct`` in
#: ``src/components/wow/ScoreDensityHistogram.tsx``: the dashboard falls back to
#: bucketing ``pct`` client-side when a grade predates this field, so a run that
#: emits the field and one that does not must land in the same bars.
_HISTOGRAM_BUCKETS: tuple[str, ...] = (
    "0-10%", "10-20%", "20-30%", "30-40%", "40-50%",
    "50-60%", "60-70%", "70-80%", "80-90%", "90-100%",
)

#: Bucket for tasks whose payload carries no sector. GDPVal tasks always do,
#: but a blank must not silently vanish from a breakdown whose task counts are
#: expected to sum to ``graded_tasks``.
_UNKNOWN_SECTOR = "Unknown"


def _score_bucket(pct: float) -> str:
    """Return the histogram bucket for a 0-100 task score."""
    if pct >= 100.0:
        return _HISTOGRAM_BUCKETS[-1]
    if pct < 0.0:
        return _HISTOGRAM_BUCKETS[0]
    return _HISTOGRAM_BUCKETS[min(9, int(pct // 10))]


def _rate(numerator: int, denominator: int) -> float:
    """Rounded pass rate as a 0-1 fraction, 0.0 when nothing was counted."""
    return round((numerator / denominator) if denominator else 0.0, 4)


def _new_item_counters() -> dict[str, int]:
    return {
        "all_items": 0,
        "all_pass": 0,
        "pre_items": 0,
        "pre_pass": 0,
        "judge_items": 0,
        "judge_pass": 0,
        "judge_errors": 0,
        "critical_items": 0,
        "critical_pass": 0,
    }


def _tally_item(counters: dict[str, int], item: dict) -> None:
    """Fold one rubric item into a counter bag.

    The run-wide summary and every per-sector breakdown call this one
    function. A second copy of these rules for the sector view would drift the
    first time someone edited one of them, and the dashboard would then show
    sector rates that do not roll up to the header they sit under.
    """
    score_excluded = bool(item.get("score_excluded", False))
    if not score_excluded:
        counters["all_items"] += 1
        if item.get("verdict") == "pass":
            counters["all_pass"] += 1
    if item.get("decided_by") == "precheck":
        if not score_excluded:
            counters["pre_items"] += 1
            if item.get("verdict") == "pass":
                counters["pre_pass"] += 1
    if item.get("decided_by") == "judge":
        counters["judge_items"] += 1
        if item.get("verdict") == "pass" and not score_excluded:
            counters["judge_pass"] += 1
        if item.get("verdict") == "judge_error":
            counters["judge_errors"] += 1
    # PR1 task 101 — critical_item_pass_rate uses sign-aware
    # MAGNITUDE_THRESHOLD (|max_score| >= 4) and ItemGrade
    # .model_did_right (filled by core.grader._aggregate in
    # PR1 task 100), NOT raw `verdict == 'pass'`.
    #
    # The legacy `(max_score or 0) >= 3` here was both
    # wrong-threshold (project convention is 4) and wrong-sign
    # (negative penalty items were excluded entirely, and
    # 'pass' on a negative item meant the model violated).
    # See data/grades/_validation/SCORE_MATH_AUDIT.md.
    if not score_excluded and _is_critical_item(item.get("max_score")):
        counters["critical_items"] += 1
        if bool(item.get("model_did_right", False)):
            counters["critical_pass"] += 1


def _severity_weight(max_score: Any) -> int | float | None:
    """Normalize a rubric ``max_score`` into a groupable curve weight."""
    try:
        weight = float(max_score)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(weight):
        return None
    return int(weight) if weight.is_integer() else weight


def _tally_severity(totals: dict[int | float, list[int]], item: dict) -> None:
    """Group one scored item by rubric weight for the severity curve.

    Counts ``model_did_right`` rather than ``verdict == 'pass'``. GDPVal
    rubrics carry negative-weight anti-criteria where a 'pass' verdict means
    the model *did* the prohibited thing, and this curve deliberately spans
    both signs — a raw verdict count would invert exactly the points the chart
    exists to show.
    """
    if bool(item.get("score_excluded", False)):
        return
    weight = _severity_weight(item.get("max_score"))
    if weight is None:
        return
    bucket = totals.setdefault(weight, [0, 0])
    bucket[0] += 1
    if bool(item.get("model_did_right", False)):
        bucket[1] += 1


def _score_exclusion_stats(
    scored_tasks: list[dict],
    avg_pct: float | None,
) -> dict:
    """What the headline average gains from rubric items that went unread.

    A rubric item the judge could not decide is marked ``score_excluded`` and
    dropped from the numerator *and* the denominator, so the task is scored
    out of less than the rubric is worth. The percentage therefore rises when
    grading fails, which is the wrong direction: on the published 30-task
    cohort ``a328feea`` earned 18.6 points and reported 84.55% out of 22 after
    two items were excluded, where the same 18.6 points out of the rubric's
    full 24 is 77.50%. Fourteen tasks of the 185-task corpus carry a
    denominator that moved this way, and until now the run said only that
    ``judge_error_rate`` was nonzero -- never that the headline had been
    lifted by it.

    ``avg_score_pct_full_denominator`` is the same average with every
    excluded item counted at its full weight and zero award. It is the
    pessimistic end: it assumes an unread item would have earned nothing,
    where ``avg_score_pct`` assumes it would have earned at the rate of the
    items that *were* read. The run's true average is between the two. The
    gap between them is ``avg_score_pct_lift``, and it is exactly zero on a
    run where the grader read every rubric it was given -- which is the point
    of publishing it: a reader can tell at a glance whether the headline
    needs the caveat at all.

    Counted over the tasks the headline averages, i.e. those without an
    ``error``. A task whose every item was excluded already leaves the
    average entirely and is counted in ``error_tasks`` instead.

    Recomputed from ``items`` rather than read from the per-task
    ``pct_full_denominator`` field, so that a grade file written before that
    field existed reports the same numbers when it is re-summarised.
    """
    tasks_with_exclusions = 0
    excluded_items = 0
    excluded_max_score = 0.0
    full_pcts: list[float] = []

    for task in scored_tasks:
        pct = float(task["pct"])
        excluded = [
            item for item in task.get("items", [])
            if item.get("score_excluded")
        ]
        excluded_max = sum(
            max(0.0, float(item.get("max_score") or 0.0)) for item in excluded
        )
        if not excluded:
            # Nothing left this rubric, so the denominator never moved and the
            # published figure is already the full-denominator one. Reusing it
            # rather than recomputing keeps the lift at a hard zero instead of
            # a rounding artefact.
            full_pcts.append(pct)
            continue

        tasks_with_exclusions += 1
        excluded_items += len(excluded)
        excluded_max_score += excluded_max

        total_awarded = float(task.get("total_awarded") or 0.0)
        full_max = float(task.get("total_max") or 0.0) + excluded_max
        full_pcts.append(
            max(0.0, min(100.0, total_awarded / full_max * 100.0))
            if full_max else 0.0
        )

    avg_full = (sum(full_pcts) / len(full_pcts)) if full_pcts else None
    return {
        "tasks_with_excluded_items": tasks_with_exclusions,
        "excluded_items": excluded_items,
        "excluded_max_score": round(excluded_max_score, 4),
        "avg_score_pct_full_denominator": (
            round(avg_full, 2) if avg_full is not None else None
        ),
        "avg_score_pct_lift": (
            round(avg_pct - avg_full, 2)
            if avg_pct is not None and avg_full is not None
            else None
        ),
    }


#: Both visual-budget markers carry their figures in the same shape, set by
#: ``Grader._task_visual_budget_error``:
#: ``task_visual_budget_exceeded:required_calls=134,cap=72``.
_VISUAL_BUDGET_FIGURES = re.compile(r"required_calls=(\d+),cap=(\d+)")


def _visual_budget_figures(marker: object) -> tuple[int, int] | None:
    """``(required_calls, cap)`` from a budget marker, or ``None``."""
    if not isinstance(marker, str):
        return None
    match = _VISUAL_BUDGET_FIGURES.search(marker)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _visual_budget_stats(task_dicts: list[dict]) -> dict:
    """What this run gave up, or lost outright, to the visual call cap.

    A task may want more renders than the per-task cap allows. The grader
    answers by dropping the escalation that exists only for unreadable files,
    and if that is still not enough, every item that wanted a picture is
    excluded. A task with nothing left to score is then dropped from the
    corpus -- not scored zero, *dropped*: it reports
    ``all_items_score_excluded`` and lands in ``error_tasks`` beside tasks
    that broke for unrelated reasons. Stage 3's ``43dc9778`` went exactly
    that way, 134 renders against a cap of 72, a 67-item task scoring 87%,
    gone from a 185-task corpus with no number anywhere saying so.

    Counted over **every** task rather than the scored ones, because the case
    this exists to surface is precisely the task that is no longer scored.
    That is the difference from ``score_exclusions``, which reports on the
    tasks the headline averages.

    The two counts overlap on purpose. ``tasks_downgraded`` is graded work
    that reached a verdict without pictures it asked for -- absorbed into the
    average, and until now invisible there. ``tasks_unmet`` is the shortfall
    that stood anyway. A task whose demand fell but stayed over the cap is in
    both.

    ``max_required_calls`` against ``call_cap`` makes headroom legible
    without going and finding it: the recovered ``43dc9778`` used 68 of 72.
    Both are ``None`` on a run where no task came near the cap, because
    nothing records a demand that was met -- ``tasks_over_cap: 0`` is the
    claim being made there, and it is the honest one.
    """
    tasks_over_cap = 0
    tasks_downgraded = 0
    tasks_unmet = 0
    items_downgraded = 0
    required_calls: list[int] = []
    caps: list[int] = []

    for task in task_dicts:
        fallback = task.get("visual_budget_fallback")
        unmet = task.get("visual_budget_unmet")
        if fallback:
            tasks_downgraded += 1
        if unmet:
            tasks_unmet += 1
        if fallback or unmet:
            tasks_over_cap += 1
        items_downgraded += sum(
            1
            for item in task.get("items", [])
            if item.get("visual_budget_downgraded")
        )
        for marker in (fallback, unmet):
            figures = _visual_budget_figures(marker)
            if figures is None:
                continue
            required_calls.append(figures[0])
            caps.append(figures[1])

    return {
        "tasks_over_cap": tasks_over_cap,
        "tasks_downgraded": tasks_downgraded,
        "tasks_unmet": tasks_unmet,
        "items_downgraded": items_downgraded,
        "max_required_calls": max(required_calls) if required_calls else None,
        # Constant within a run, since it is read once from config; ``max``
        # only picks a representative if a resumed run ever spans a change.
        "call_cap": max(caps) if caps else None,
    }


#: The routes an item can be graded on, as ``grade.schema.json`` fixes them.
#: Listed here so that every one of them gets a count once routing is being
#: recorded at all -- including the routes this run happened not to use, which
#: is the answer to "how many audio items?" and not a gap in the record.
_ROUTING_MODALITIES = ("visual", "audio", "formatting", "text", "mixed")


def _routing_stats(task_dicts: list[dict]) -> dict:
    """How much of this run each sub-judge decided.

    Every item already carries ``routing_modality``; nothing aggregated it, so
    the size of a route was only ever obtainable by downloading the payload and
    counting it by hand. That is the wrong place for it to live once a route's
    trustworthiness is in question: the audio sub-judge measures at a
    discrimination of 0.00 against synthetic clips whose answers are known, and
    the question that follows -- how much of the published score rests on it --
    is a property of the run, so the run says it.

    Three numbers, because three different questions get asked:

    ``items`` is the population, over **every** task including errored ones.
    This is the "31 of 8,816" figure, and it is the one to quote about the
    corpus.

    ``scored_items`` and ``scored_max_score`` are over the items that actually
    moved the headline: not ``score_excluded``, inside a task without an
    ``error``. Scoped exactly like :func:`_score_exclusion_stats`, deliberately
    -- two summarisers over one payload must not disagree about which items the
    average is made of. ``scored_max_score`` sums positive rubric weight only,
    the same convention and for the same reason as ``excluded_max_score``: a
    penalty item's negative weight is not weight that would leave a denominator.

    ``tasks`` counts tasks touching a route at least once, so a route worth one
    item spread over ten tasks is distinguishable from one worth ten items in a
    single task. Over every task, like ``items``.

    **A route absent from a run that recorded routing is a measured zero. A
    route absent from a run that recorded none is not.** Grades written before
    routing existed carry ``routing_modality: null`` on every item, and
    zero-filling those into ``audio: 0`` would turn "never asked" into "asked
    and found none" -- the one reading this field exists to prevent. So the
    maps are empty when nothing was recorded, ``unrecorded_items`` carries the
    whole item count, and ``recorded`` says which of the two situations a
    reader is in. A partly-instrumented payload reports both: real counts and a
    non-zero ``unrecorded_items``.

    A modality outside the schema's enum is counted under its own name rather
    than dropped, so a route added upstream shows up here before anything
    downstream has been taught the word.

    Recomputed from ``items``, so a merged shard set reports what a serial run
    would have, and a payload published before this field existed reports the
    same numbers when it is re-summarised.
    """
    items: dict[str, int] = {}
    scored_items: dict[str, int] = {}
    scored_max_score: dict[str, float] = {}
    tasks: dict[str, int] = {}
    unrecorded_items = 0

    for task in task_dicts:
        scored_task = not task.get("error")
        seen_here: set[str] = set()
        for item in task.get("items", []):
            modality = item.get("routing_modality")
            if not isinstance(modality, str) or not modality:
                unrecorded_items += 1
                continue
            items[modality] = items.get(modality, 0) + 1
            seen_here.add(modality)
            if scored_task and not item.get("score_excluded"):
                scored_items[modality] = scored_items.get(modality, 0) + 1
                scored_max_score[modality] = scored_max_score.get(
                    modality, 0.0
                ) + max(0.0, float(item.get("max_score") or 0.0))
        for modality in seen_here:
            tasks[modality] = tasks.get(modality, 0) + 1

    if not items:
        return {
            "recorded": False,
            "items": {},
            "scored_items": {},
            "scored_max_score": {},
            "tasks": {},
            "unrecorded_items": unrecorded_items,
        }

    names = sorted(set(_ROUTING_MODALITIES) | set(items))
    return {
        "recorded": True,
        "items": {name: items.get(name, 0) for name in names},
        "scored_items": {name: scored_items.get(name, 0) for name in names},
        "scored_max_score": {
            name: round(scored_max_score.get(name, 0.0), 4) for name in names
        },
        "tasks": {name: tasks.get(name, 0) for name in names},
        "unrecorded_items": unrecorded_items,
    }


def _grader_agreement_stats(task_dicts: list[dict]) -> dict:
    """Whether two gradings of one task were ever put side by side here.

    ``openai_compat.inconsistent_count`` is a required integer that has been
    the literal ``0`` in every payload this repository has ever written, and
    the dashboard renders it as *"multiple graders scored the same task
    differently: 0"*. No run has ever had multiple graders. Each task is
    graded once, and ``step9_merge_shards`` refuses a merge whose shards are
    not disjoint, so a published payload cannot hold the same task twice.
    Nothing was compared, and the number for "nothing was compared" was
    published as the number for "they all agreed".

    The direction matters. The repository has measured this separately: three
    gradings of the same thirty answers, at one grader fingerprint, moved
    **29 of the 30 tasks**. So the zero is not an unexamined guess that
    happens to be defensible -- it is the reassuring answer to a question
    whose real answer is already known to be the opposite.

    That integer stays as it is. Ninety-four committed payloads carry it,
    ``core/grade_payload.py`` and ``scripts/aggregate-grades.mjs`` both use
    ``inconsistent_count != 0`` to recognise a stub, and its schema entry now
    says plainly what it is. What was missing is a statement of the *basis*,
    which is what this returns: ``compared`` says whether any task in this
    payload was graded more than once, and ``tasks_that_moved`` is ``None``
    when none was -- never ``0``, for the same reason ``routing`` reports
    empty maps rather than ``audio: 0`` on a run that never recorded a route.

    Nothing here assumes the current pipeline's answer. The counts come out
    of the payload, so a set of tasks that does hold repeats -- assembled by
    something other than the merge step, or by a later summariser that reads
    repeat runs together -- gets a real measurement out of this rather than a
    constant, and the branch that says so is reached by the tests either way.

    Two gradings differ when their ``pct`` differs; a grading with no numeric
    ``pct`` (an errored task) has no score to compare, so a task needs two of
    them before it counts as compared at all.
    """
    scores_by_task: dict[str, list[float]] = {}
    gradings_by_task: dict[str, int] = {}

    for task in task_dicts:
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            continue
        gradings_by_task[task_id] = gradings_by_task.get(task_id, 0) + 1
        pct = task.get("pct")
        if isinstance(pct, bool) or not isinstance(pct, (int, float)):
            continue
        scores_by_task.setdefault(task_id, []).append(float(pct))

    gradings_per_task = max(gradings_by_task.values(), default=0)
    comparable = [scores for scores in scores_by_task.values() if len(scores) > 1]

    if not comparable:
        return {
            "compared": False,
            "gradings_per_task": gradings_per_task,
            "tasks_compared": 0,
            "tasks_that_moved": None,
            "max_spread_pp": None,
        }

    moved = 0
    widest = 0.0
    for scores in comparable:
        spread = max(scores) - min(scores)
        if spread > 0:
            moved += 1
        widest = max(widest, spread)

    return {
        "compared": True,
        "gradings_per_task": gradings_per_task,
        "tasks_compared": len(comparable),
        "tasks_that_moved": moved,
        "max_spread_pp": round(widest, 4),
    }


def _compute_summary(
    task_dicts: list[dict],
    *,
    unpriced_models: list[str] | None = None,
) -> dict:
    total = len(task_dicts)
    scored_tasks = [task for task in task_dicts if not task.get("error")]
    graded_tasks = len(scored_tasks)
    error_tasks = total - graded_tasks
    pcts = [float(task["pct"]) for task in scored_tasks]
    avg_pct = (sum(pcts) / len(pcts)) if pcts else None

    # Both names are inherited and both are looser than they sound: `perfect`
    # is >= 99%, not full marks, and `zero` is <= 1%, not nothing. The values
    # are right; only the words for them were ever wrong, which is why no check
    # of the numbers caught it. Anything that prints these has to print the
    # threshold beside them -- see `openai_compat` in schemas/grade.schema.json.
    perfect = sum(1 for x in pcts if x >= 99.0)
    zero = sum(1 for x in pcts if x <= 1.0)
    partial = graded_tasks - perfect - zero

    counters = _new_item_counters()
    sector_counters: dict[str, dict[str, int]] = {}
    sector_pcts: dict[str, list[float]] = {}
    severity_totals: dict[int | float, list[int]] = {}
    sign_aware_verdicts = False

    main_calls = 0
    main_in_tok = 0
    main_out_tok = 0
    main_cached_tok = 0
    main_latency_ms = 0.0
    perception_calls = 0
    perception_in_tok = 0
    perception_out_tok = 0
    perception_cached_tok = 0
    perception_latency_ms = 0.0
    render_calls = 0
    render_latency_ms = 0.0
    usage_complete = True

    for task in task_dicts:
        main_calls += int(task.get("judge_call_count", 0))
        main_in_tok += int(task.get("judge_input_tokens", 0))
        main_out_tok += int(task.get("judge_output_tokens", 0))
        main_cached_tok += int(task.get("judge_cached_tokens", 0))
        main_latency_ms += float(task.get("judge_total_latency_ms", 0.0))
        perception_calls += int(task.get("perception_call_count", 0))
        perception_in_tok += int(task.get("perception_input_tokens", 0))
        perception_out_tok += int(task.get("perception_output_tokens", 0))
        perception_cached_tok += int(task.get("perception_cached_tokens", 0))
        perception_latency_ms += float(
            task.get("perception_total_latency_ms", 0.0)
        )
        render_calls += int(task.get("render_call_count", 0))
        render_latency_ms += float(task.get("render_total_latency_ms", 0.0))
        # A row that does not answer has not said yes. The counters just above
        # default a missing token count to 0, so a silent row makes the total
        # smaller; if its silence also read as "complete", the run would
        # publish a figure it never measured and claim it was whole. `is True`
        # rather than `bool(...)`: a `1` or a `"true"` that arrived from
        # somewhere is not this producer's boolean either.
        usage_complete = usage_complete and (
            task.get("usage_complete") is True
        )

        # The sector breakdown is defined over graded tasks, so its task counts
        # sum to `graded_tasks`. An errored task carries no rubric items, so
        # nothing is lost from the item rates by scoping it this way.
        sector_bag: dict[str, int] | None = None
        if not task.get("error"):
            sector = str(task.get("sector") or "").strip() or _UNKNOWN_SECTOR
            sector_pcts.setdefault(sector, []).append(float(task["pct"]))
            sector_bag = sector_counters.setdefault(
                sector, _new_item_counters()
            )

        for item in task.get("items", []):
            _tally_item(counters, item)
            _tally_severity(severity_totals, item)
            if sector_bag is not None:
                _tally_item(sector_bag, item)
            if "model_did_right" in item:
                sign_aware_verdicts = True

    by_sector = {
        sector: {
            "task_count": len(sector_pcts[sector]),
            "avg_pct": round(
                sum(sector_pcts[sector]) / len(sector_pcts[sector]), 2
            ),
            "critical_item_pass_rate": _rate(
                bag["critical_pass"], bag["critical_items"]
            ),
            "precheck_pass_rate": _rate(bag["pre_pass"], bag["pre_items"]),
            "judge_pass_rate": _rate(bag["judge_pass"], bag["judge_items"]),
        }
        for sector, bag in sorted(sector_counters.items())
    }

    histogram_counts = dict.fromkeys(_HISTOGRAM_BUCKETS, 0)
    for pct in pcts:
        histogram_counts[_score_bucket(pct)] += 1
    # Every bucket is emitted, including empty ones, so the chart draws a full
    # axis instead of collapsing to whichever scores happened to occur.
    score_density_histogram = [
        {"bucket": bucket, "count": histogram_counts[bucket]}
        for bucket in _HISTOGRAM_BUCKETS
    ]

    # Grades written before ``core.grader`` began emitting ``model_did_right``
    # (PR1 task 100) carry no sign-aware verdict, so every point on the curve
    # would read 0.0 and the chart would assert a total failure that never
    # happened. A single rate can absorb that; a curve cannot, because its
    # shape is the claim. Publish nothing rather than a false shape — the
    # component already renders an empty state for a missing field.
    rubric_severity_curve = (
        [
            {
                "weight": weight,
                "n_items": n_items,
                "pass_rate": _rate(n_did_right, n_items),
            }
            for weight, (n_items, n_did_right) in sorted(severity_totals.items())
        ]
        if sign_aware_verdicts
        else []
    )

    return {
        "total_tasks": total,
        "graded_tasks": graded_tasks,
        "error_tasks": error_tasks,
        "openai_compat": {
            "avg_score_pct": round(avg_pct, 2) if avg_pct is not None else None,
            "ci_pct": round(_ci_pct(pcts), 2) if pcts else None,
            "perfect_count": perfect,
            "zero_count": zero,
            "partial_count": partial,
            "inconsistent_count": 0,
        },
        # Sits beside the headline rather than inside it: ``openai_compat`` is
        # a fixed compatibility shape, and this is the caveat on the number it
        # carries, not another field of it.
        "score_exclusions": _score_exclusion_stats(scored_tasks, avg_pct),
        # The basis behind `openai_compat.inconsistent_count`, which is the
        # constant 0 above and is read downstream as "the graders agreed".
        # This says whether anything was compared to reach it.
        "grader_agreement": _grader_agreement_stats(task_dicts),
        # Over every task, not just the scored ones. A task that could not fit
        # its renders may have left the average altogether, and that is the
        # case this is here to count -- see `_visual_budget_stats`.
        "visual_budget": _visual_budget_stats(task_dicts),
        # Which sub-judge decided how much of this run. Beside the two above
        # rather than inside `wow`: those are rates about how the grading went,
        # and this is the composition of what was graded.
        "routing": _routing_stats(task_dicts),
        "wow": {
            "rubric_item_coverage_avg": _rate(
                counters["all_pass"], counters["all_items"]
            ),
            "critical_item_pass_rate": _rate(
                counters["critical_pass"], counters["critical_items"]
            ),
            "precheck_pass_rate": _rate(
                counters["pre_pass"], counters["pre_items"]
            ),
            "judge_pass_rate": _rate(
                counters["judge_pass"], counters["judge_items"]
            ),
            "judge_error_rate": canonical_rate(
                counters["judge_errors"], counters["judge_items"]
            ),
            "by_sector": by_sector,
            # Left empty deliberately. The GDPVal rubrics carry no category
            # taxonomy — rubric items have an id, a criterion string and a
            # weight, and nothing that groups them into categories — so there
            # is no source for this breakdown. Populating it would mean
            # inventing a taxonomy and presenting it as measurement.
            # SectorHeatmap.tsx already treats it as absent and falls back to
            # the per-sector rates above.
            "by_rubric_category": {},
            "score_density_histogram": score_density_histogram,
            "rubric_severity_curve": rubric_severity_curve,
        },
        "cost": {
            "total_judge_calls": main_calls + perception_calls,
            "total_main_judge_calls": main_calls,
            "total_perception_calls": perception_calls,
            "total_input_tokens": main_in_tok + perception_in_tok,
            "total_output_tokens": main_out_tok + perception_out_tok,
            "total_cached_tokens": main_cached_tok + perception_cached_tok,
            "main_input_tokens": main_in_tok,
            "main_output_tokens": main_out_tok,
            "main_cached_tokens": main_cached_tok,
            "perception_input_tokens": perception_in_tok,
            "perception_output_tokens": perception_out_tok,
            "perception_cached_tokens": perception_cached_tok,
            "estimated_cost_usd": None,
            "pricing_complete": False,
            "unpriced_models": sorted(set(unpriced_models or [])),
            "total_judge_latency_sec": round(
                (main_latency_ms + perception_latency_ms) / 1000.0, 2
            ),
            "total_main_judge_latency_sec": round(
                main_latency_ms / 1000.0, 2
            ),
            "total_perception_latency_sec": round(
                perception_latency_ms / 1000.0, 2
            ),
            "total_render_calls": render_calls,
            "total_render_latency_sec": round(render_latency_ms / 1000.0, 2),
            "usage_complete": usage_complete,
        },
        # The priced counterpart to the token counters above. Read back off
        # the task rows rather than off the live ledger, so that the total a
        # reader sees is the sum of the receipts a reader can see: a resumed
        # run's earlier tasks were written by an earlier process, and a merged
        # shard's ledger may be long gone, but their rows are right here.
        BUCKET_GRADING: summarise_receipts([
            CostReceipt.from_dict(task.get(BUCKET_GRADING))
            for task in task_dicts
        ]).as_dict(),
    }


def _resolve_inference_model(
    inf_results: dict, exp_config: ExperimentConfig | None
) -> str:
    """Return the deployment that actually produced the inference output.

    Priority:
      1. inf_results['model']  — what step2 (or HF reconstruct) recorded
      2. exp_config.condition_a.model.deployment — fallback to the
         experiment yaml (source of truth for the inference run)
      3. '' — defensive default

    Inference vs judge are different pipelines. Never fall back to
    config['judge']['model'] here — that would silently mislead the UI.
    """
    candidate = (inf_results.get("model") or "").strip()
    if candidate:
        return candidate
    if exp_config is not None:
        deployment = getattr(getattr(exp_config.condition_a, "model", None), "deployment", "")
        if deployment and str(deployment).strip():
            return str(deployment).strip()
    return ""


def _resolve_source_inference_run_dir(source_id: str) -> str | None:
    """Best-effort: return repo-relative path to the inference run directory.

    Returns ``"batch-runner/results/<source_id>"`` if that directory exists
    (relative to the current working directory of step8, which is the
    repo-root or batch-runner/). Otherwise None (debug-only field per spec).
    """
    if not source_id:
        return None
    candidate = Path("results") / source_id
    if candidate.exists():
        # step8 is invoked from inside batch-runner/, so prefix that segment
        # to produce a repo-root-relative path consistent with the spec.
        return f"batch-runner/results/{source_id}"
    return None


def _build_grade_payload(
    exp_name: str,
    inf_results: dict,
    config: dict,
    config_hash: str,
    loader: RubricLoader,
    prompt_version: str,
    task_dicts: list[dict],
    grader_source_hash: str,
    source_inference_repo_id: str | None,
    source_inference_revision: str | None,
    azure_ai_runtime_fingerprint: str,
    azure_ai_routes: list[dict[str, str]],
    run_status: str = "final",
    expected_task_ids: list[str] | None = None,
    exp_config: ExperimentConfig | None = None,
    source_experiment_id: str | None = None,
    renderer_fingerprint: dict[str, str] | None = None,
    cost_ledger: dict[str, str] | None = None,
) -> dict:
    if run_status not in {"partial", "final", "diagnostic"}:
        raise ValueError("grade run_status is invalid")
    expected_ids = list(expected_task_ids or [row["task_id"] for row in task_dicts])
    expected_ids = [canonical_task_id(value) for value in expected_ids]
    if len(expected_ids) != len(set(expected_ids)):
        raise ValueError("expected grade task IDs must be unique")
    if re.fullmatch(r"[0-9a-f]{64}", azure_ai_runtime_fingerprint) is None:
        raise ValueError("primary grader runtime fingerprint is invalid")
    if (
        not azure_ai_routes
        or azure_ai_routes[0].get("workload") != "grader"
        or azure_ai_routes[0].get("runtime_fingerprint")
        != azure_ai_runtime_fingerprint
    ):
        raise ValueError("primary grader route identity is invalid")
    src_id = (source_experiment_id or exp_name or "").strip() or exp_name
    return {
        "schema_version": SCHEMA_VERSION,
        "run_status": run_status,
        "expected_task_count": len(expected_ids),
        "expected_ordered_task_ids_sha256": _ordered_task_ids_sha256(expected_ids),
        "experiment_id": exp_name,
        "experiment_yaml_name": exp_name,
        "source_inference_experiment_id": src_id,
        "source_inference_run_dir": _resolve_source_inference_run_dir(src_id),
        "source_inference_repo_id": source_inference_repo_id,
        "source_inference_revision": source_inference_revision,
        "source_azure_ai_routes": inf_results.get("azure_ai_routes", []),
        "source_azure_ai_provenance_status": inf_results.get(
            "azure_ai_provenance_status", "local-runtime"
        ),
        "azure_ai_routes": list(azure_ai_routes),
        "azure_ai_runtime_fingerprint": azure_ai_runtime_fingerprint,
        "grader_source_hash": grader_source_hash,
        "renderer_fingerprint": renderer_fingerprint,
        "anchor_projection": config.get("anchor_projection"),
        "inference_model": _resolve_inference_model(inf_results, exp_config),
        "inference_completed_at": inf_results.get("completed_at"),
        "judge": {
            "provider": config["judge"]["provider"],
            "api": config["judge"]["api"],
            "model": config["judge"]["model"],
            "deployment": config["judge"].get("deployment", config["judge"]["model"]),
            "api_version": config["judge"].get("api_version", ""),
            "reasoning_effort": config.get("judge", {}).get("reasoning", {}).get("effort", "high"),
            "temperature": config.get("judge", {}).get("generation", {}).get("temperature", 0),
            "seed": config.get("judge", {}).get("generation", {}).get("seed", 42),
            "perception": config.get("judge", {}).get("perception", {}),
            # The resolved value, not the configured one. A config that omits
            # file_cap_per_item still grades under a cap, and a grade file that
            # only carried the perception block verbatim would leave a reader
            # inferring it from whichever revision of the code ran.
            "visual_file_cap": resolve_visual_file_cap(config.get("judge") or {}),
            "config_name": config.get("config_name", "unknown"),
            "config_hash": config_hash,
        },
        "rubric": {
            "source": config.get("rubric", {}).get("source", "huggingface"),
            "repo_id": config["rubric"]["repo_id"],
            "revision": config["rubric"]["revision"],
            "commit_sha": loader.rubric_sha,
            "short_sha": loader.rubric_short_sha,
        },
        "prompt": {
            "template": config["prompt"]["template"],
            "version": prompt_version,
        },
        "graded_at": _now_iso(),
        "graded_by": "step8_grade.py",
        "graded_by_version": GRADED_BY_VERSION,
        # Where the per-call audit trail for this run's grading costs was
        # written, and its digest. ``None`` where no ledger was kept, which is
        # a different claim from a ledger showing nothing.
        "cost_ledger": cost_ledger,
        "tasks": task_dicts,
        "summary": _compute_summary(
            task_dicts,
            unpriced_models=_unpriced_models(config),
        ),
    }


def _validate_schema(payload: dict) -> None:
    schema = _read_schema()
    validate_grade_payload(payload, schema)


def _print_dry_run_stats(tasks: list[dict], loader: RubricLoader) -> None:
    precheck = 0
    judge = 0
    for t in tasks:
        rubric = loader.load(t["task_id"])
        for item in rubric.rubric_items:
            mode, _ = Grader._classify(item)
            if mode == "precheck":
                precheck += 1
            else:
                judge += 1
    total = precheck + judge
    print(f"Dry-run tasks={len(tasks)} items={total} precheck={precheck} judge={judge}")


def main() -> int:
    args = parse_args()

    config_path = Path(args.config)
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    validate_grading_config(config)
    config_hash = hash_config(str(config_path))

    try:
        exp_config = load_experiment_yaml(args.experiment_yaml_name)
    except Exception as exc:
        print(f"ERROR: experiment yaml load failed: {exc}", file=sys.stderr)
        return 1

    if args.source == "local":
        try:
            inf_results = load_local_inference_results()
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: inference results unavailable or invalid: {exc}", file=sys.stderr)
            return 2
    else:
        print("ERROR: --source hf is not implemented in Phase A. Use scripts/download_inference_from_hf.py first.", file=sys.stderr)
        return 2

    try:
        inference_repo_id, inference_revision = resolve_source_inference_identity(
            inf_results, str(config.get("schema_version", ""))
        )
    except ValueError as exc:
        print(f"ERROR: inference identity validation failed: {exc}", file=sys.stderr)
        return 1

    try:
        grader_source_hash = compute_grader_source_hash(config_path, config)
    except (KeyError, OSError, ValueError) as exc:
        print(f"ERROR: grader source hash failed: {exc}", file=sys.stderr)
        return 1

    try:
        loader = RubricLoader(
            repo_id=config["rubric"]["repo_id"],
            revision=config["rubric"]["revision"],
            cache_dir=config["rubric"]["cache_dir"],
        )
        rubric_sha = loader.rubric_sha
        rubric_short_sha = loader.rubric_short_sha
    except Exception as exc:
        print(f"ERROR: rubric loader init failed: {exc}", file=sys.stderr)
        return 3

    judge_slug = _judge_slug(config["judge"]["model"])
    prompt_v = config["prompt"]["version"]
    try:
        tasks, config_pinned_scope = filter_tasks_for_config(
            inf_results,
            config,
            tasks_csv=args.tasks,
            limit=args.limit,
        )
    except ValueError as exc:
        print(f"ERROR: invalid grading task selection: {exc}", file=sys.stderr)
        return 1

    try:
        _validate_pinned_rerun_identity(
            config,
            # The config it opened, not the path that opened it. The same
            # `rerun_identity.experiment_id` is checked a second time by
            # scripts/download_inference_from_hf.py against what the inference
            # run recorded, and that recording is the declared id -- so a
            # grading config would otherwise have to pin two different spellings
            # to satisfy both halves of one run.
            experiment_id=exp_config.experiment_id,
            task_ids=[task["task_id"] for task in tasks],
            rubric_commit_sha=rubric_sha,
            inference_revision=inference_revision,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    expected_task_ids = [task["task_id"] for task in tasks]
    source_provenance_status = inf_results.get(
        "azure_ai_provenance_status", "local-runtime"
    )
    # A pre-sidecar inference carries no Azure AI route provenance. That is a
    # gap in the audit trail, not in the graded corpus — the judge never reads
    # those routes; only the deliverables, rubric, and prompts reach it. So the
    # gap blocks publication when the *scope* is unproven too, and stops
    # blocking once the config pins the complete corpus in canonical order.
    # `--allow-legacy-missing-provenance` on the downloader pins nothing, so a
    # bare CLI override still lands in the diagnostic tree.
    legacy_provenance_unbounded = (
        source_provenance_status == "legacy-missing"
        and config_pinned_scope != "complete"
    )
    # A gold corpus is the benchmark's own expert answers, graded to find out
    # how high the grader can score at all. No model wrote it and no model
    # could enter it in a leaderboard, so it never takes the canonical output
    # path — `scripts/aggregate-grades.mjs` reads that path and has no way to
    # say "this is the ceiling, not a competitor". Unlike the scope rules
    # above, pinning the complete corpus does not lift this: what makes it
    # unpublishable is what it is, not how much of it was graded.
    gold_corpus_run = source_provenance_status == GOLD_PROVENANCE_STATUS
    diagnostic_run = (
        config_pinned_scope == "subset"
        or args.tasks is not None
        or args.limit > 0
        or legacy_provenance_unbounded
        or gold_corpus_run
    )
    completed_run_status = "diagnostic" if diagnostic_run else "final"
    # Sharding deliberately does NOT feed `diagnostic_run` above. A diagnostic
    # run is one whose *scope* was narrowed (--tasks/--limit/pinned selection),
    # which forks the output into _diagnostic/<scope_sha>/. A shard's scope is
    # still the full corpus; only the division of labour changed. Keeping them
    # separate is what lets every shard resolve to the same canonical
    # out_path and merge back into one final payload.
    sharded_run = args.shard_count > 1
    # `completed_run_status` keeps meaning "what a COMPLETE run of this config
    # looks like" — the cache/resume guards compare against it. What this
    # process actually writes is a partial when it is one shard of many.
    emitted_run_status = "partial" if sharded_run else completed_run_status
    diagnostic_task_scope_sha = (
        _ordered_task_ids_sha256(expected_task_ids)
        if diagnostic_run
        else None
    )
    try:
        out_path = resolve_grade_output_path(
            config,
            experiment_id=args.experiment_yaml_name,
            judge_slug=judge_slug,
            config_hash=config_hash,
            rubric_sha=rubric_sha,
            rubric_short_sha=rubric_short_sha,
            prompt_version=prompt_v,
            inference_sha=inference_revision,
            grader_source_hash=grader_source_hash,
            diagnostic_task_scope_sha=diagnostic_task_scope_sha,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
            run_ordinal=args.run_ordinal,
        )
        _write_github_output("grade_file", _repo_relative_grade_file(out_path))
        _write_github_output("grade_status", emitted_run_status)
    except (KeyError, ValueError) as exc:
        print(f"ERROR: grade output path resolution failed: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        _print_dry_run_stats(
            _shard_slice(
                tasks,
                shard_index=args.shard_index,
                shard_count=args.shard_count,
            ),
            loader,
        )
        return 0

    try:
        azure_ai_routes = preflight_routes(
            grader_route_workloads(config),
            **grader_transport_options(config),
        )
        primary_runtime_fingerprint = azure_ai_routes[0][
            "runtime_fingerprint"
        ]
    except ValueError as exc:
        print(f"ERROR: Azure AI route validation failed: {exc}", file=sys.stderr)
        return 1
    try:
        tasks = validate_local_deliverables(
            tasks, Path("workspace") / "upload"
        )
    except ValueError as exc:
        print(f"ERROR: deliverable tree validation failed: {exc}", file=sys.stderr)
        return 1

    # From here `tasks` is the corpus *identity* — it drives expected_task_count,
    # expected_ordered_task_ids_sha256 and every resume/cache guard, and stays
    # the full corpus even when this process only grades a slice of it.
    # `shard_tasks` is this process's *workload*. Identical when unsharded.
    shard_tasks = _shard_slice(
        tasks, shard_index=args.shard_index, shard_count=args.shard_count
    )
    if sharded_run:
        print(
            f"SHARD {args.shard_index + 1}/{args.shard_count}: grading "
            f"{len(shard_tasks)} of {len(tasks)} tasks"
        )

    renderer_fingerprint: dict[str, str] | None = None
    renderer_required = requires_track2_office_renderer(config)
    if renderer_required:
        try:
            renderer_fingerprint = get_renderer_fingerprint()
        except ReadDeliverableError as exc:
            print(
                f"ERROR: Track 2 renderer fingerprint failed: {exc}",
                file=sys.stderr,
            )
            return 1

    if out_path.exists() and not args.force and not args.resume:
        try:
            existing = _load_existing_grade(out_path)
            _validate_azure_ai_resume_identity(
                existing,
                azure_ai_routes,
                primary_runtime_fingerprint,
            )
            _validate_grade_resume_identity(
                existing,
                experiment_id=args.experiment_yaml_name,
                rubric_commit_sha=rubric_sha,
                prompt_version=prompt_v,
                config_hash=config_hash,
                source_inference_repo_id=inference_repo_id,
                source_inference_revision=inference_revision,
                grader_source_hash=grader_source_hash,
                renderer_fingerprint=(
                    renderer_fingerprint if renderer_required else None
                ),
                anchor_projection=config.get("anchor_projection"),
            )
            if sharded_run:
                # A completed shard leaves a partial, not a final, and that
                # partial must be THIS shard's slice — otherwise we would skip
                # on a sibling shard's output and silently never grade our own.
                existing_ids = _validate_grade_task_set(
                    existing, tasks, require_complete=False
                )
                shard_ids = set(_task_ids(shard_tasks, label="current shard"))
                if existing_ids != shard_ids:
                    raise ValueError(
                        "existing partial at this path belongs to a different "
                        f"shard: expected {len(shard_ids)} ids for "
                        f"--shard-index {args.shard_index}, found "
                        f"{len(existing_ids)}"
                    )
            else:
                _validate_grade_task_set(
                    existing,
                    tasks,
                    require_complete=True,
                    complete_status=completed_run_status,
                )
        except ValueError as exc:
            print(f"ERROR: grade cache identity validation failed: {exc}", file=sys.stderr)
            return 1
        print(
            f"SKIP - exists: {out_path}. "
            "Use --force to overwrite or --resume to continue."
        )
        return 0

    if args.resume and not out_path.exists():
        print(
            f"ERROR: --resume partial not found at {out_path}; "
            "refusing to start a fresh paid run",
            file=sys.stderr,
        )
        return 1

    task_payloads: list[dict] = []
    completed_task_ids: set[str] = set()

    if args.resume and out_path.exists():
        try:
            existing = _load_existing_grade(out_path)
            existing_tasks = existing["tasks"]
            _validate_azure_ai_resume_identity(
                existing,
                azure_ai_routes,
                primary_runtime_fingerprint,
            )
        except ValueError as exc:
            print(
                f"ERROR: --resume could not load existing partial "
                f"{out_path}: {exc}",
                file=sys.stderr,
            )
            return 1

        try:
            _validate_grade_resume_identity(
                existing,
                experiment_id=args.experiment_yaml_name,
                rubric_commit_sha=loader.rubric_sha,
                prompt_version=prompt_v,
                config_hash=config_hash,
                source_inference_repo_id=inference_repo_id,
                source_inference_revision=inference_revision,
                grader_source_hash=grader_source_hash,
                renderer_fingerprint=(
                    renderer_fingerprint if renderer_required else None
                ),
                anchor_projection=config.get("anchor_projection"),
            )
            completed_task_ids = _validate_grade_task_set(
                existing, tasks, require_complete=False
            )
            if sharded_run:
                # The partial may be short (that is what resuming means), but
                # every id in it must belong to this shard's slice. Anything
                # else means we picked up a sibling shard's file and would
                # re-emit its tasks under our index, double-counting on merge.
                shard_ids = set(_task_ids(shard_tasks, label="current shard"))
                foreign = sorted(completed_task_ids - shard_ids)
                if foreign:
                    raise ValueError(
                        "partial contains tasks outside --shard-index "
                        f"{args.shard_index} of {args.shard_count}: {foreign}"
                    )
        except ValueError as exc:
            print(f"ERROR: --resume {exc}", file=sys.stderr)
            return 1

        task_payloads = list(existing_tasks)
        print(
            f"[resume] loaded {len(completed_task_ids)} previously graded "
            f"tasks from {out_path}",
            file=sys.stderr,
        )

    # ── Per-task grading cost receipts (task 0828) ──
    #
    # One ledger per grade file, opened before the judge so that the judge's
    # client and its perception readers are already metered on the first task.
    # It lives beside the grade file and is append-only: a resumed chunk, and
    # the next chunk after that, reopen this same ledger and add to it. What an
    # abandoned attempt cost stays in it, because it was still spent.
    #
    # `continue_rounds` is how a resume avoids colliding with the chunk before
    # it. Step 8 keeps no round counter of its own — a resumed run only knows
    # which tasks are already done — so the round is read off the ledger's size.
    cost_ledger_path = out_path.with_name(out_path.stem + ".cost_ledger.sqlite3")
    cost_export_path = out_path.with_name(out_path.stem + ".cost_ledger.jsonl")
    cost_run_id = make_cost_run_id(
        experiment_yaml_name=args.experiment_yaml_name,
        config_hash=config_hash,
        grader_source_hash=grader_source_hash,
        run_ordinal=args.run_ordinal,
    )

    # The paragraph above describes a ledger that outlives its chunk, and on a
    # developer's machine it does. In CI it did not: every chunk gets a fresh
    # runner with an empty workspace, so the sqlite3 a previous chunk filled in
    # was gone before the next one looked for it, and each chunk opened an
    # empty ledger and exported only its own calls. What does survive is the
    # JSONL, which the workflow commits beside the grade file — so that is what
    # the ledger is rebuilt from here.
    #
    # This has to happen *before* the recorder is opened. ``continue_rounds``
    # reads the round number off the ledger's size, and the round is folded
    # into every call identifier; a ledger seeded afterwards would hand this
    # chunk identifiers the previous one had already used, and importing those
    # later would look like a contradiction rather than a duplicate.
    if cost_export_path.is_file() and not cost_ledger_path.exists():
        try:
            seed = CostReceiptLedger(cost_ledger_path, run_id=cost_run_id)
            try:
                recovered = seed.import_jsonl(cost_export_path)
            finally:
                seed.close()
            print(
                f"[cost] recovered {recovered} records from "
                f"{cost_export_path.name}",
                file=sys.stderr,
            )
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            print(
                f"[cost] ledger recovery from {cost_export_path.name} failed "
                f"({type(exc).__name__}); this chunk's receipts will cover "
                "this chunk only",
                file=sys.stderr,
            )

    cost_recorder, cost_ledger_note = open_cost_recorder(
        cost_ledger_path,
        run_id=cost_run_id,
        continue_rounds=True,
    )
    if cost_ledger_note:
        print(f"[cost] {cost_ledger_note}", file=sys.stderr)

    # The ledger is a sqlite database, and exporting one that has been closed
    # raises rather than returning nothing. Both facts below exist to keep the
    # export strictly before the close on every path out of this function; see
    # ``close_grader`` for why the ordering is not obvious.
    ledger_closed = False
    last_ledger_digest: str | None = None

    def cost_ledger_pointer() -> dict[str, str] | None:
        """Export the ledger and return the pointer a saved grade carries.

        Called at each save rather than once at the end, because a partial is a
        published result too and its pointer has to match the ledger as it
        stood when that partial was written. A failed export returns ``None``:
        a grade that cannot point at its own audit trail says so, instead of
        carrying a digest of something else.

        A ledger written outside the repository returns ``None`` for the same
        reason. The field is a *relative repository path* — that is what this
        file's schema says, what ``cost_projection`` validates, and what
        ``cost-receipt.mjs`` re-derives — and for a long while what went into
        it was ``Path.name``, a bare filename that resolved from nowhere. A
        local run writing its ledger somewhere else has no repository path to
        give, and a name is not a smaller version of one.
        """
        if cost_recorder is None:
            return None
        try:
            digest = cost_recorder.ledger.export_jsonl(cost_export_path)
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            print(
                f"[cost] ledger export failed ({type(exc).__name__})",
                file=sys.stderr,
            )
            return None
        relative = repo_relative_ledger_path(cost_export_path, _repo_root())
        if relative is None:
            print(
                f"[cost] ledger is outside the repository ({cost_export_path});"
                " the grade will not claim one",
                file=sys.stderr,
            )
            return None
        return ledger_reference(relative, digest)

    def flush_cost_ledger() -> None:
        """Put the ledger on disk wherever this run ends, including badly.

        Exporting at each save is right for the pointer a saved grade carries
        and wrong for keeping the record, because a run that never saves never
        exports. Shard 4 of the first Stage 3 attempt is the case: it graded
        six tasks over five hours, hit the job's own timeout inside the
        seventh, saved nothing — ``partial_save_every_n_tasks`` is 10 — and
        left no artifact behind, so five hours of paid calls are recorded
        nowhere at all.

        This runs on every return, on an unhandled exception, and on the
        SIGTERM a cancelled job arrives as. It publishes the path and digest as
        step outputs too, so the workflow can preserve them without having to
        guess where they are.

        It refuses to run once the ledger is shut. ``atexit`` unwinds in
        reverse order of registration, so on the paths that do not go through
        ``finish`` — the crash and the cancellation, which are the ones this
        exists for — ``close_grader`` runs first and closes the database out
        from under this. Exporting then raises ``ProgrammingError`` and prints
        an export failure, which is both the wrong outcome (nothing is
        written) and the wrong message (it reads as loss on the normal path,
        where the ledger is already safely on disk). The flush is therefore
        performed by ``close_grader`` immediately before it closes, and this
        guard makes the later call a silent no-op.
        """
        nonlocal last_ledger_digest
        if cost_recorder is None or ledger_closed:
            return
        try:
            digest = cost_recorder.ledger.export_jsonl(cost_export_path)
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            print(
                f"[cost] final ledger export failed ({type(exc).__name__})",
                file=sys.stderr,
            )
            return
        if digest == last_ledger_digest:
            # Already reported, and nothing has been recorded since. Saying it
            # twice invites the reader to look for two ledgers.
            return
        last_ledger_digest = digest
        print(
            f"[cost] ledger → {cost_export_path.name} sha256={digest}",
            file=sys.stderr,
        )
        try:
            _write_github_output(
                "cost_ledger_file", _repo_relative_grade_file(cost_export_path)
            )
            _write_github_output("cost_ledger_sha256", digest)
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            print(
                f"[cost] could not publish the ledger pointer "
                f"({type(exc).__name__})",
                file=sys.stderr,
            )

    atexit.register(flush_cost_ledger)
    for _signum in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(_signum, _exit_on_signal)
        except (ValueError, OSError):  # not the main thread, or unsupported
            pass

    def grading_receipt(task_id: str) -> dict:
        """This task's grading receipt, or an explicit reason there is none.

        ``when_empty`` is ``complete`` on purpose. Reaching this line means the
        task *was* graded; a task graded entirely by rule, with no judge call
        at all, really did cost nothing, and that is the one honest ``$0``. A
        run with no ledger is the other case and reports ``unavailable``.
        """
        if cost_recorder is None:
            return CostReceipt.unavailable().as_dict()
        return cost_recorder.receipt_for(
            task_id, BUCKET_GRADING, when_empty=STATUS_COMPLETE
        ).as_dict()

    def record_task_progress(
        task, rubric_item_ids: list[str], draft, resumed_items: int
    ) -> int:
        """Keep the finished items of a task the clock interrupted.

        Returns how many items this chunk added, which is what
        ``out_of_time_exit`` uses to decide whether asking for another paid
        chunk is honest. Zero on every path that does not write a file, so a
        chunk that could not save progress does not get credit for it.

        Three refusals, and all three end the same way — no file, no credit,
        the task marked from item one next time:

        * no draft, because the grader that raised predates this or was built
          through a path that never installed one;
        * no forward motion, so the next chunk would read back exactly what
          this one read in and the loop would repeat at full price;
        * a draft holding the whole rubric, which is a finished task and
          belongs in the partial as a grade. ``load_checkpoint`` refuses one
          too; refusing to write it as well means the contradiction never
          reaches disk in the first place.

        Failure to write is reported and swallowed. A chunk that graded real
        items must not lose them to a full disk in the progress directory —
        the partial is the thing that has to persist, and it already has.
        """
        if draft is None:
            return 0
        completed = len(draft.completed_items)
        advanced = completed - resumed_items
        if advanced <= 0:
            return 0
        if completed >= len(rubric_item_ids):
            print(
                f"[progress] {task.task_id}: refusing to file a complete "
                "rubric as progress",
                file=sys.stderr,
            )
            return 0
        try:
            path = write_checkpoint(
                out_path,
                build_progress(
                    task_id=task.task_id,
                    grader_source_hash=grader_source_hash,
                    rubric_item_ids=rubric_item_ids,
                    draft=draft,
                ),
            )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            print(
                f"[progress] {task.task_id}: could not save progress "
                f"({type(exc).__name__}); the task will be graded whole next "
                "chunk",
                file=sys.stderr,
            )
            return 0
        print(
            f"[progress] {task.task_id}: {completed}/{len(rubric_item_ids)} "
            f"items kept (+{advanced} this chunk) → {path.name}",
            file=sys.stderr,
        )
        try:
            # Published for the same reason the ledger is: a chunk gets a
            # fresh runner, so a file that is not committed does not exist by
            # the time the next chunk looks for it.
            _write_github_output(
                "grade_progress_file", _repo_relative_grade_file(path)
            )
            _write_github_output("grade_progress_sha256", digest)
        except (OSError, ValueError) as exc:
            published = os.getenv("GITHUB_OUTPUT")
            print(
                f"[progress] could not publish the progress pointer "
                f"({type(exc).__name__}); the file is on disk at {path}",
                file=sys.stderr,
            )
            if published:
                # Under a workflow an unpublished pointer means an uncommitted
                # file, and an uncommitted file is gone before the next chunk
                # runs. Asking for a paid resume on the strength of progress
                # that will not be there is the dishonest half of this.
                print(
                    "[progress] no pointer means no commit; this chunk does "
                    "not count as having moved",
                    file=sys.stderr,
                )
                return 0
        return advanced

    try:
        config["_runtime"] = {
            "experiment_id": args.experiment_yaml_name,
            "rubric_sha": loader.rubric_sha,
            "azure_ai_runtime_fingerprint": primary_runtime_fingerprint,
        }
        grader = Grader(
            config=config, rubric_loader=loader, cost_recorder=cost_recorder
        )
    except BaseException as exc:
        print(
            "ERROR: judge initialization failed: "
            f"{public_provider_error_text(exc)}",
            file=sys.stderr,
        )
        if cost_recorder is not None:
            flush_cost_ledger()
            ledger_closed = True
            cost_recorder.ledger.close()
        return 4

    def close_grader() -> None:
        nonlocal grader
        nonlocal ledger_closed
        active_grader = grader
        grader = None
        try:
            close = getattr(active_grader, "close", None)
            if callable(close):
                close()
        except BaseException as exc:
            print(
                "ERROR: judge cleanup failed: "
                f"{public_provider_error_text(exc)}",
                file=sys.stderr,
            )
        # After the judge, never before: closing the ledger first would leave
        # a client that is still being shut down writing to a closed database.
        if cost_recorder is not None:
            # The last chance to export, and on a crash or a cancellation the
            # only one. This function is registered with ``atexit`` after
            # ``flush_cost_ledger`` and so unwinds before it, which means a run
            # that does not reach ``finish`` arrives here with the ledger still
            # unexported. Flushing from inside the close is what makes the
            # ordering true by construction instead of by registration order.
            try:
                flush_cost_ledger()
            except BaseException as exc:
                print(
                    f"ERROR: cost ledger export failed: {type(exc).__name__}",
                    file=sys.stderr,
                )
            ledger_closed = True
            try:
                cost_recorder.ledger.close()
            except BaseException as exc:
                print(
                    f"ERROR: cost ledger cleanup failed: {type(exc).__name__}",
                    file=sys.stderr,
                )

    grader_exit_cleanup = atexit.register(close_grader)

    try:
        azure_ai_runtime_fingerprint = getattr(
            grader,
            "runtime_fingerprint",
            None,
        )
    except BaseException as exc:
        print(
            "ERROR: grader route verification failed: "
            f"{public_provider_error_text(exc)}",
            file=sys.stderr,
        )
        try:
            close_grader()
        finally:
            atexit.unregister(grader_exit_cleanup)
        return 4
    if azure_ai_runtime_fingerprint != primary_runtime_fingerprint:
        print(
            "ERROR: grader client route differs from preflight provenance",
            file=sys.stderr,
        )
        try:
            close_grader()
        finally:
            atexit.unregister(grader_exit_cleanup)
        return 4

    partial_every = int(config.get("output", {}).get("partial_save_every_n_tasks", 10))
    initial_completed_count = len(task_payloads)

    # Time guard: pre-empt GH Actions hard 6h limit. Default 4h (14400s)
    # leaves ~80 min for the workflow's retrigger + setup overhead and the
    # final partial save. Caller can override via env (e.g. shorter budgets
    # for tighter chunks, or longer for self-hosted runners).
    time_budget_sec = int(os.getenv("GRADER_TIME_BUDGET_SEC", "14400"))
    grade_loop_start = time.monotonic()

    # A finished task belongs on disk within this long, whatever the task
    # count says. ``partial_save_every_n_tasks`` counts tasks, and a shard
    # holds seventeen of them, so the first checkpoint of a default run falls
    # after the tenth — which shard 4 of the first Stage 3 attempt never
    # reached. It finished six, spent four more hours inside the seventh, and
    # was killed with an empty output directory. Six tasks were graded and
    # paid for twice.
    partial_save_max_interval_sec = float(
        config.get("output", {}).get("partial_save_max_interval_sec", 900)
    )
    last_partial_save = grade_loop_start
    # Seeded from the loop's own start rather than a second reading of the
    # clock. They denote the same instant, and taking it once means the
    # budget and the checkpoint interval are measured from a common origin
    # instead of from two points a few microseconds apart.

    def out_of_time() -> bool:
        return (
            time_budget_sec > 0
            and (time.monotonic() - grade_loop_start) > time_budget_sec
        )

    # Installed here rather than passed to the constructor because the budget
    # is measured from the loop, not from the judge's setup. The grader calls
    # this between rubric items and between split children, so the budget is
    # reachable from inside a task instead of only between tasks.
    grader.should_stop = out_of_time

    GRADE_EXIT_RESUME = 7  # contract with grade-run.yml's auto-trigger step
    GRADE_EXIT_PERSISTENCE_FAILURE = 5
    GRADE_EXIT_RUNTIME_FAILURE = 6

    prompt_version = grader.prompt_version

    def build_payload(run_status: str) -> dict:
        return _build_grade_payload(
            args.experiment_yaml_name,
            inf_results,
            config,
            config_hash,
            loader,
            prompt_version,
            task_payloads,
            grader_source_hash,
            inference_repo_id,
            inference_revision,
            azure_ai_runtime_fingerprint=azure_ai_runtime_fingerprint,
            azure_ai_routes=azure_ai_routes,
            run_status=run_status,
            expected_task_ids=expected_task_ids,
            exp_config=exp_config,
            source_experiment_id=args.source_experiment_id,
            renderer_fingerprint=renderer_fingerprint,
            cost_ledger=cost_ledger_pointer(),
        )

    def save_checkpoint(run_status: str, *, verify: bool = True) -> None:
        """Write the tasks finished so far, and prove the file readable.

        ``verify`` re-reads and compares because the paths that end the run
        get one chance at persistence; the periodic checkpoint skips it, since
        another one follows shortly and a torn write there costs minutes
        rather than the chunk.
        """
        nonlocal last_partial_save
        payload = build_payload(run_status)
        _validate_schema(payload)
        _save_json(out_path, payload)
        if verify:
            persisted = _load_existing_grade(out_path)
            _validate_schema(persisted)
            if persisted != payload:
                raise ValueError(f"persisted {run_status} does not match payload")
        last_partial_save = time.monotonic()

    def finish(code: int) -> int:
        try:
            flush_cost_ledger()
        finally:
            try:
                close_grader()
            finally:
                atexit.unregister(grader_exit_cleanup)
        return code

    def out_of_time_exit(note: str, *, items_advanced: int = 0) -> int:
        """Stop, keep what is finished, and say whether resuming is worth it.

        Exit 7 asks the workflow for another paid chunk, and that is only
        honest if this chunk moved the shard forward. A chunk that finished
        nothing would hand the next one the same first task and the same
        result, charging for the loop each time — so it stops the shard
        instead and leaves a human to look at the task that is eating the
        budget.

        ``items_advanced`` is the second way forward. One task in the gold
        corpus is longer than a chunk: ``9e39df84`` has 57 items and four paid
        attempts stopped at 45, 54, 54 and 55 of them. Measured in whole
        tasks every one of those chunks finished nothing, so this guard was
        right to refuse — and the shard could never finish, because refusing
        was also the only answer available. A chunk that left more graded
        items behind than it started with has moved, and the next chunk starts
        from them rather than from item one.

        The elapsed time is read here rather than taken from the caller so
        that the loop asks the clock once per task, in ``out_of_time``. A
        second read alongside it is not merely redundant: it moves the
        decision one tick later than the number that gets reported for it.
        """
        elapsed_sec = time.monotonic() - grade_loop_start
        graded_count = len(task_payloads)
        remaining = len(shard_tasks) - graded_count
        if graded_count <= initial_completed_count and items_advanced <= 0:
            print(
                f"[time-guard] {note}; no new task completed in this chunk; "
                "refusing to request another paid resume",
                file=sys.stderr,
            )
            return finish(GRADE_EXIT_PERSISTENCE_FAILURE)
        if graded_count <= initial_completed_count:
            print(
                f"[time-guard] {note}; no task finished, but {items_advanced} "
                "more rubric items are on disk than this chunk started with",
                file=sys.stderr,
            )
        print(
            f"\n[time-guard] {note}: elapsed {elapsed_sec/60:.1f}min > budget "
            f"{time_budget_sec/60:.0f}min; graded={graded_count}/{len(shard_tasks)} "
            f"remaining={remaining}. Saving partial and requesting resume.",
            file=sys.stderr,
        )
        try:
            save_checkpoint("partial")
            print(f"[time-guard] partial saved → {out_path}", file=sys.stderr)
        except Exception as save_exc:
            import traceback
            print(f"[time-guard] partial save FAILED: {save_exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return finish(GRADE_EXIT_PERSISTENCE_FAILURE)
        return finish(GRADE_EXIT_RESUME)

    for idx, task_result in enumerate(shard_tasks, start=1):
        # Resume skip
        if task_result["task_id"] in completed_task_ids:
            continue

        # Time-budget pre-check (before starting an expensive judge call)
        if out_of_time():
            return out_of_time_exit("between tasks")

        task = loader.load(task_result["task_id"])
        deliverable_dir = resolve_deliverable_dir(task_result)
        rubric_item_ids = [item.rubric_item_id for item in task.rubric_items]

        # Items an earlier chunk finished inside this same task, if it left
        # any. ``None`` is the ordinary case — first attempt, nothing on disk.
        resume_progress = None
        try:
            resume_progress = load_checkpoint(
                out_path,
                task_id=task.task_id,
                grader_source_hash=grader_source_hash,
                rubric_item_ids=rubric_item_ids,
            )
        except CheckpointRejected as refused:
            # Said out loud. A refused checkpoint means a fingerprint or a
            # rubric moved under a paid run, and the task is about to be
            # re-marked from item one at full price; that is the correct
            # answer and an expensive one, so it does not happen quietly.
            print(
                f"[progress] {task.task_id}: {refused.reason}; "
                "grading the task whole",
                file=sys.stderr,
            )
        resumed_items = (
            len(resume_progress.completed_items) if resume_progress else 0
        )
        if resumed_items:
            print(
                f"[progress] {task.task_id}: resuming after {resumed_items}/"
                f"{len(rubric_item_ids)} items",
                file=sys.stderr,
            )

        task_started = time.perf_counter()
        try:
            grade = grader.grade_task(
                task, deliverable_dir, resume_from=resume_progress
            )
        except GradingDeadlineExceeded as expired:
            # The task is still dropped whole rather than saved half-marked:
            # an unfinished task scored on the items it got through would read
            # as failing the ones it never reached. What changes is that the
            # finished items are kept beside the partial instead of thrown
            # away, so the next chunk continues from them. Whatever this chunk
            # spent is in the ledger either way, because it was spent.
            print(f"[time-guard] {expired}", file=sys.stderr)
            advanced = record_task_progress(
                task, rubric_item_ids, expired.progress, resumed_items
            )
            return out_of_time_exit(
                f"inside {task.task_id}", items_advanced=advanced
            )
        # Graded whole. The progress file described an unfinished task and now
        # describes nothing, so it goes.
        discard_checkpoint(out_path, task.task_id)
        grading_wall_time_ms = (time.perf_counter() - task_started) * 1000.0
        row = _task_to_dict(
            grade,
            grading_wall_time_ms=grading_wall_time_ms,
        )
        # Stamped here, once, while this task's calls are the newest in the
        # ledger — not recomputed at save time. A resumed chunk loads the
        # earlier chunk's rows verbatim, so what an earlier process recorded
        # for an earlier task stays exactly as that process recorded it.
        row[BUCKET_GRADING] = grading_receipt(row["task_id"])
        runtime_error = None
        if config.get("schema_version") == "2.0":
            runtime_error = _track2_task_runtime_error(row)
            if runtime_error is not None and not row.get("error"):
                row["error"] = runtime_error
            if runtime_error is None and row.get("usage_complete") is not True:
                # Not an error, and deliberately not stamped as one: this
                # task's marking is as good as every other task's, so it keeps
                # its score and stays in the sector breakdown and the item
                # rates. Only the bill is unknown, and this row's own
                # `usage_complete: false` already says so — `summary.cost`
                # folds it in, and the receipt for the task is filed partial.
                # Said out loud here because a run that quietly stops being
                # priceable is the thing worth noticing.
                print(
                    f"WARNING: {row['task_id']} reported incomplete token "
                    "usage; its grades stand, but this run's cost total is "
                    "no longer complete.",
                    file=sys.stderr,
                )
        task_payloads.append(row)

        print(
            f"[{idx}/{len(shard_tasks)}] {task.task_id[:8]} -> {grade.pct:.1f}% "
            f"({grade.total_awarded:.1f}/{grade.total_max})"
        )

        if runtime_error is not None:
            try:
                save_checkpoint("diagnostic")
            except Exception as save_exc:
                print(
                    f"ERROR: Track 2 runtime diagnostic save failed: {save_exc}",
                    file=sys.stderr,
                )
                return finish(GRADE_EXIT_PERSISTENCE_FAILURE)
            print(
                "ERROR: Track 2 grading stopped after runtime failure "
                f"for {task.task_id}: {runtime_error}",
                file=sys.stderr,
            )
            return finish(GRADE_EXIT_RUNTIME_FAILURE)

        due_by_count = partial_every > 0 and idx % partial_every == 0
        due_by_clock = (
            partial_save_max_interval_sec > 0
            and (time.monotonic() - last_partial_save) > partial_save_max_interval_sec
        )
        if due_by_count or due_by_clock:
            try:
                save_checkpoint("partial", verify=False)
            except Exception as save_exc:
                import traceback
                print(
                    f"\n!! PARTIAL SAVE FAILED at idx={idx} task={task.task_id[:8]} !!",
                    file=sys.stderr,
                )
                print(
                    f"   Exception: {type(save_exc).__name__}: {save_exc}",
                    file=sys.stderr,
                )
                traceback.print_exc(file=sys.stderr)
                raise

    final = build_payload(emitted_run_status)
    _validate_schema(final)
    _save_json(out_path, final)

    avg = final["summary"]["openai_compat"]["avg_score_pct"]
    avg_text = "unscored" if avg is None else f"{avg:.2f}"
    print(
        f"Completed grading: tasks={len(task_payloads)}, "
        f"avg_pct={avg_text}, out={out_path}"
    )
    return finish(0)


if __name__ == "__main__":
    sys.exit(main())
