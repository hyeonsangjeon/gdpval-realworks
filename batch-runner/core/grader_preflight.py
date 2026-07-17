"""Model-free task planning for Track 2 grading cohorts."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from core.deliverable_selector import plan_targets_for_criterion
from core.grader import Grader
from core.grader_routing import Modality, resolve_runtime_routing
from core.rubric_loader import TaskRubric
from core.tool_calling_judge import ToolCallingJudge


def _planner(config: dict) -> Grader:
    """Build only the local precheck surface; never initialize an API client."""
    grader = object.__new__(Grader)
    grader.config = config
    return grader


def plan_task_runtime(
    config: dict,
    task: TaskRubric,
    deliverable_dir: str | Path,
) -> dict[str, Any]:
    """Return the exact model-free routing plan for one local task."""
    grader = _planner(config)
    deliverable_path = Path(deliverable_dir)
    files = grader._list_files(deliverable_path)
    selection = grader._select_deliverables(task, deliverable_path, files)
    file_map = grader._relative_file_map(deliverable_path, files)

    routes: Counter[str] = Counter()
    precheck_candidates = 0
    precheck_resolved = 0
    precheck_fallbacks = 0
    planned_main_judgments = 0
    planned_visual_calls = 0
    planned_audio_calls = 0
    unsupported_visual_paths: list[str] = []
    item_plans: list[dict[str, Any]] = []
    errors: list[str] = []

    if selection.selection_status != "ok":
        errors.append(
            f"selection_status={selection.selection_status}:"
            f"{selection.selection_error or 'unavailable'}"
        )

    targets = {target.target_id: target for target in selection.primary_targets}
    for item in task.rubric_items:
        target_plan = plan_targets_for_criterion(selection, item.criterion)
        mode, pattern_id = grader._classify(item)
        item_plan: dict[str, Any] = {
            "rubric_item_id": item.rubric_item_id,
            "criterion": item.criterion,
            "target_scope": target_plan.target_scope,
            "selected_paths": list(target_plan.selected_paths),
            "precheck_pattern_id": pattern_id,
        }

        if target_plan.target_scope == "selection_error":
            item_plan["outcome"] = "selection_error"
            item_plans.append(item_plan)
            continue

        if target_plan.target_scope == "split_children":
            child_routes: list[str] = []
            raw_visual_paths: list[str] = []
            raw_audio_routes = 0
            for target_id in target_plan.target_ids:
                target = targets.get(target_id)
                if target is None:
                    errors.append(
                        f"{item.rubric_item_id}: missing target {target_id}"
                    )
                    continue
                decision = resolve_runtime_routing(item.criterion, target.paths)
                child_routes.append(decision.modality.value)
                if decision.modality is Modality.VISUAL:
                    raw_visual_paths.extend(target.paths)
                elif decision.modality is Modality.AUDIO:
                    raw_audio_routes += 1
            parent_route = (
                child_routes[0]
                if child_routes and len(set(child_routes)) == 1
                else "mixed"
            )
            routes[parent_route] += 1
            visual_paths: list[str] = []
            visual_error: str | None = None
            if raw_visual_paths:
                planned_names, visual_error = (
                    ToolCallingJudge.validate_planned_visual_names(
                        raw_visual_paths
                    )
                )
                if visual_error is not None:
                    errors.append(f"{item.rubric_item_id}: {visual_error}")
                    unsupported_visual_paths.extend(
                        sorted(
                            set(planned_names)
                            - set(
                                ToolCallingJudge.planned_supported_visual_names(
                                    planned_names
                                )
                            )
                        )
                    )
                else:
                    visual_paths = planned_names
                    planned_visual_calls += len(visual_paths)
            if visual_error is None:
                planned_main_judgments += len(child_routes)
                planned_audio_calls += raw_audio_routes
            item_plan.update({
                "outcome": (
                    "judge" if visual_error is None else "preflight_error"
                ),
                "routing_modality": parent_route,
                "child_routes": child_routes,
                "planned_visual_paths": visual_paths,
                "planned_audio_calls": (
                    raw_audio_routes if visual_error is None else 0
                ),
            })
            item_plans.append(item_plan)
            continue

        selected_files = grader._paths_for_selected(
            target_plan.selected_paths, file_map
        )
        if not selected_files:
            errors.append(f"{item.rubric_item_id}: no selected target files")
            item_plan["outcome"] = "selection_error"
            item_plans.append(item_plan)
            continue

        if mode == "precheck":
            precheck_candidates += 1
            precheck = grader._run_precheck(pattern_id, item, selected_files)
            if precheck is not None:
                precheck_resolved += 1
                item_plan.update({
                    "outcome": "precheck",
                    "precheck_verdict": precheck[0],
                })
                item_plans.append(item_plan)
                continue
            precheck_fallbacks += 1

        decision = resolve_runtime_routing(
            item.criterion, target_plan.selected_paths
        )
        routes[decision.modality.value] += 1
        supported: list[str] = []
        visual_error: str | None = None
        if decision.modality is Modality.VISUAL:
            planned_names, visual_error = (
                ToolCallingJudge.validate_planned_visual_names(
                    target_plan.selected_paths
                )
            )
            if visual_error is not None:
                errors.append(f"{item.rubric_item_id}: {visual_error}")
                unsupported_visual_paths.extend(
                    sorted(
                        set(planned_names)
                        - set(
                            ToolCallingJudge.planned_supported_visual_names(
                                planned_names
                            )
                        )
                    )
                )
            else:
                supported = planned_names
                planned_visual_calls += len(supported)
        if visual_error is None:
            planned_main_judgments += 1
            if decision.modality is Modality.AUDIO:
                planned_audio_calls += 1
        item_plan.update({
            "outcome": (
                "judge" if visual_error is None else "preflight_error"
            ),
            "routing_modality": decision.modality.value,
            "matched_keywords": list(decision.matched_keywords),
            "planned_visual_paths": supported,
            "planned_audio_calls": (
                1 if decision.modality is Modality.AUDIO else 0
            ),
        })
        item_plans.append(item_plan)

    unsupported_visual_paths = sorted(set(unsupported_visual_paths))
    visual_config = (
        (config.get("judge") or {}).get("perception") or {}
    ).get("visual") or {}
    audio_config = (
        (config.get("judge") or {}).get("perception") or {}
    ).get("audio") or {}
    visual_cap = visual_config.get("call_cap_per_task")
    if (
        isinstance(visual_cap, int)
        and planned_visual_calls > visual_cap
    ):
        errors.append(
            "task visual budget exceeded: "
            f"planned={planned_visual_calls}, cap={visual_cap}"
        )
    audio_cap = audio_config.get("call_cap_per_task")
    if isinstance(audio_cap, int) and planned_audio_calls > audio_cap:
        errors.append(
            "task audio budget exceeded: "
            f"planned={planned_audio_calls}, cap={audio_cap}"
        )
    if planned_audio_calls:
        if not audio_config.get("model"):
            errors.append("audio routes require configured audio perception")
        errors.append(
            "audio perception calls are model-selected and cannot be exact: "
            f"routes={planned_audio_calls}"
        )

    return {
        "task_id": task.task_id,
        "selection": selection.to_dict(),
        "rubric_items": len(task.rubric_items),
        "precheck_candidates": precheck_candidates,
        "precheck_resolved": precheck_resolved,
        "precheck_fallbacks": precheck_fallbacks,
        "judge_routes": dict(sorted(routes.items())),
        "planned_main_judgments": planned_main_judgments,
        "planned_render_calls": planned_visual_calls,
        "planned_audio_calls": planned_audio_calls,
        "planned_perception_calls": planned_visual_calls + planned_audio_calls,
        "visual_call_cap": visual_cap,
        "audio_call_cap": audio_cap,
        "unsupported_visual_paths": unsupported_visual_paths,
        "errors": errors,
        "items": item_plans,
    }


def summarize_cohort(task_plans: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate task plans without losing their ordered task identity."""
    routes: Counter[str] = Counter()
    for task in task_plans:
        routes.update(task["judge_routes"])
    return {
        "task_count": len(task_plans),
        "ordered_task_ids": [task["task_id"] for task in task_plans],
        "rubric_items": sum(task["rubric_items"] for task in task_plans),
        "precheck_candidates": sum(
            task["precheck_candidates"] for task in task_plans
        ),
        "precheck_resolved": sum(
            task["precheck_resolved"] for task in task_plans
        ),
        "precheck_fallbacks": sum(
            task["precheck_fallbacks"] for task in task_plans
        ),
        "judge_routes": dict(sorted(routes.items())),
        "planned_main_judgments": sum(
            task["planned_main_judgments"] for task in task_plans
        ),
        "planned_render_calls": sum(
            task["planned_render_calls"] for task in task_plans
        ),
        "planned_audio_calls": sum(
            task["planned_audio_calls"] for task in task_plans
        ),
        "planned_perception_calls": sum(
            task["planned_perception_calls"] for task in task_plans
        ),
        "errors": [
            f"{task['task_id']}: {error}"
            for task in task_plans
            for error in task["errors"]
        ],
        "tasks": task_plans,
    }