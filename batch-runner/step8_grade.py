#!/usr/bin/env python3
"""Step 8: Grade inference outputs with rubric-based judge.

Usage:
    python step8_grade.py exp998_smoke_baseline_sample \
      --config grading_configs/default_gpt5pro.yaml \
      --dry-run --limit 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import validate

from core.experiment_config import ExperimentConfig
from core.grader import Grader
from core.rubric_loader import RubricLoader

SCHEMA_VERSION = "1.0"
GRADED_BY_VERSION = "0.1.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def hash_config(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


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
        "--source-experiment-id",
        default=None,
        help=(
            "Phase 2 source linkage: experiment_id of the inference run that "
            "produced the deliverables being graded. Defaults to "
            "experiment_yaml_name. Useful when the grade exp name diverges "
            "from the inference run directory (e.g. re-grading a renamed run)."
        ),
    )
    return parser.parse_args()


def validate_grading_config(config: dict) -> None:
    if config.get("schema_version") != "1.0":
        raise ValueError("grading config schema_version must be 1.0")

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
    for key in ["provider", "api", "model", "endpoint_env"]:
        if key not in judge:
            raise ValueError(f"missing config key: judge.{key}")

    rubric = config.get("rubric", {})
    for key in ["repo_id", "revision", "cache_dir"]:
        if key not in rubric:
            raise ValueError(f"missing config key: rubric.{key}")

    prompt = config.get("prompt", {})
    if "template" not in prompt or "version" not in prompt:
        raise ValueError("missing config key: prompt.template/prompt.version")
    if not Path(prompt["template"]).exists():
        raise ValueError(f"prompt template not found: {prompt['template']}")

    output = config.get("output", {})
    if "directory" not in output or "filename_template" not in output:
        raise ValueError("missing config key: output.directory/output.filename_template")

    repo_id = str(rubric.get("repo_id", ""))
    if "/" not in repo_id:
        raise ValueError("rubric.repo_id must be owner/name format")

    if int(config.get("tpm_guard", {}).get("max_concurrent", 1)) < 1:
        raise ValueError("tpm_guard.max_concurrent must be >= 1")


def load_experiment_yaml(experiment_yaml_name: str) -> ExperimentConfig:
    path = Path("experiments") / f"{experiment_yaml_name}.yaml"
    return ExperimentConfig.from_yaml(str(path))


def load_local_inference_results() -> dict:
    path = Path("workspace") / "step2_inference_results.json"
    if not path.exists():
        raise FileNotFoundError(str(path))
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_tasks(inference_results: dict, tasks_csv: str | None, limit: int) -> list[dict]:
    tasks = list(inference_results.get("results", []))
    if tasks_csv:
        wanted = {x.strip() for x in tasks_csv.split(",") if x.strip()}
        tasks = [t for t in tasks if t.get("task_id") in wanted]
    if limit and limit > 0:
        tasks = tasks[:limit]
    return tasks


def resolve_deliverable_dir(task_result: dict) -> str:
    deliverable_files = task_result.get("deliverable_files") or []
    if deliverable_files:
        first = Path(deliverable_files[0])
        return str((Path("workspace") / "upload" / first.parent).resolve())
    return str((Path("workspace") / "upload" / "deliverable_files" / task_result.get("task_id", "")).resolve())


def _judge_slug(model: str) -> str:
    return model.replace(".", "_")


def _read_schema() -> dict:
    path = Path("schemas") / "grade.schema.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _ci_pct(values: list[float]) -> float:
    if not values:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(var)
    return 1.96 * std / math.sqrt(n)


def _task_to_dict(task_grade) -> dict:
    data = asdict(task_grade)
    data["graded_at"] = _now_iso()
    return data


def _compute_summary(task_dicts: list[dict]) -> dict:
    total = len(task_dicts)
    graded_tasks = sum(1 for t in task_dicts if not t.get("error"))
    error_tasks = total - graded_tasks
    pcts = [float(t["pct"]) for t in task_dicts]
    avg_pct = (sum(pcts) / len(pcts)) if pcts else 0.0

    perfect = sum(1 for x in pcts if x >= 99.0)
    zero = sum(1 for x in pcts if x <= 1.0)
    partial = total - perfect - zero

    pre_items = 0
    pre_pass = 0
    judge_items = 0
    judge_pass = 0
    judge_errors = 0
    critical_items = 0
    critical_pass = 0
    all_items = 0
    all_pass = 0

    total_calls = 0
    total_in_tok = 0
    total_out_tok = 0
    total_latency_ms = 0.0

    for task in task_dicts:
        total_calls += int(task.get("judge_call_count", 0))
        total_in_tok += int(task.get("judge_input_tokens", 0))
        total_out_tok += int(task.get("judge_output_tokens", 0))
        total_latency_ms += float(task.get("judge_total_latency_ms", 0.0))

        for item in task.get("items", []):
            all_items += 1
            if item.get("verdict") == "pass":
                all_pass += 1
            if item.get("decided_by") == "precheck":
                pre_items += 1
                if item.get("verdict") == "pass":
                    pre_pass += 1
            if item.get("decided_by") == "judge":
                judge_items += 1
                if item.get("verdict") == "pass":
                    judge_pass += 1
                if item.get("verdict") == "judge_error":
                    judge_errors += 1
            if (item.get("max_score") or 0) >= 3:
                critical_items += 1
                if item.get("verdict") == "pass":
                    critical_pass += 1

    return {
        "total_tasks": total,
        "graded_tasks": graded_tasks,
        "error_tasks": error_tasks,
        "openai_compat": {
            "avg_score_pct": round(avg_pct, 2),
            "ci_pct": round(_ci_pct(pcts), 2),
            "perfect_count": perfect,
            "zero_count": zero,
            "partial_count": partial,
            "inconsistent_count": 0,
        },
        "wow": {
            "rubric_item_coverage_avg": round((all_pass / all_items) if all_items else 0.0, 4),
            "critical_item_pass_rate": round((critical_pass / critical_items) if critical_items else 0.0, 4),
            "precheck_pass_rate": round((pre_pass / pre_items) if pre_items else 0.0, 4),
            "judge_pass_rate": round((judge_pass / judge_items) if judge_items else 0.0, 4),
            "judge_error_rate": round((judge_errors / judge_items) if judge_items else 0.0, 4),
            "by_sector": {},
            "by_rubric_category": {},
            "score_density_histogram": [],
            "rubric_severity_curve": [],
        },
        "cost": {
            "total_judge_calls": total_calls,
            "total_input_tokens": total_in_tok,
            "total_output_tokens": total_out_tok,
            "estimated_cost_usd": 0.0,
            "total_judge_latency_sec": round(total_latency_ms / 1000.0, 2),
        },
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
    exp_config: ExperimentConfig | None = None,
    source_experiment_id: str | None = None,
) -> dict:
    src_id = (source_experiment_id or exp_name or "").strip() or exp_name
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": exp_name,
        "experiment_yaml_name": exp_name,
        "source_inference_experiment_id": src_id,
        "source_inference_run_dir": _resolve_source_inference_run_dir(src_id),
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
        "tasks": task_dicts,
        "summary": _compute_summary(task_dicts),
    }


def _validate_schema(payload: dict) -> None:
    schema = _read_schema()
    validate(instance=payload, schema=schema)


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
        except FileNotFoundError:
            print("ERROR: inference results not found", file=sys.stderr)
            return 2
    else:
        print("ERROR: --source hf is not implemented in Phase A. Use scripts/download_inference_from_hf.py first.", file=sys.stderr)
        return 2

    try:
        loader = RubricLoader(
            repo_id=config["rubric"]["repo_id"],
            revision=config["rubric"]["revision"],
            cache_dir=config["rubric"]["cache_dir"],
        )
        _ = loader.rubric_short_sha
    except Exception as exc:
        print(f"ERROR: rubric loader init failed: {exc}", file=sys.stderr)
        return 3

    judge_slug = _judge_slug(config["judge"]["model"])
    prompt_v = config["prompt"]["version"]
    out_dir = Path(config["output"]["directory"])
    out_name = config["output"]["filename_template"].format(
        exp_id=args.experiment_yaml_name,
        judge_slug=judge_slug,
        rubric_short_sha=loader.rubric_short_sha,
        prompt_v=prompt_v,
    )
    out_path = out_dir / out_name

    if out_path.exists() and not args.force:
        print(f"SKIP - exists: {out_path}. Use --force to overwrite.")
        return 0

    tasks = filter_tasks(inf_results, args.tasks, args.limit)

    if args.dry_run:
        _print_dry_run_stats(tasks, loader)
        return 0

    try:
        grader = Grader(config=config, rubric_loader=loader)
    except Exception as exc:
        print(f"ERROR: judge initialization failed: {exc}", file=sys.stderr)
        return 4

    partial_every = int(config.get("output", {}).get("partial_save_every_n_tasks", 10))
    task_payloads: list[dict] = []

    for idx, task_result in enumerate(tasks, start=1):
        task = loader.load(task_result["task_id"])
        deliverable_dir = resolve_deliverable_dir(task_result)
        grade = grader.grade_task(task, deliverable_dir)
        row = _task_to_dict(grade)
        task_payloads.append(row)

        print(
            f"[{idx}/{len(tasks)}] {task.task_id[:8]} -> {grade.pct:.1f}% "
            f"({grade.total_awarded:.1f}/{grade.total_max})"
        )

        if partial_every > 0 and idx % partial_every == 0:
            try:
                partial = _build_grade_payload(
                    args.experiment_yaml_name,
                    inf_results,
                    config,
                    config_hash,
                    loader,
                    grader.prompt_version,
                    task_payloads,
                    exp_config=exp_config,
                    source_experiment_id=args.source_experiment_id,
                )
                _validate_schema(partial)
                _save_json(out_path, partial)
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

    final = _build_grade_payload(
        args.experiment_yaml_name,
        inf_results,
        config,
        config_hash,
        loader,
        grader.prompt_version,
        task_payloads,
        exp_config=exp_config,
        source_experiment_id=args.source_experiment_id,
    )
    _validate_schema(final)
    _save_json(out_path, final)

    avg = final["summary"]["openai_compat"]["avg_score_pct"]
    print(f"Completed grading: tasks={len(task_payloads)}, avg_pct={avg:.2f}, out={out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
