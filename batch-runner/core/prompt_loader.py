"""
Prompt Loader — Load and render prompt templates from YAML files.

Prompts are stored in batch-runner/prompts/*.yaml and loaded by name.
This decouples prompt content from execution logic, making it easy to
iterate on prompts without modifying Python code.

Usage:
    from core.prompt_loader import load_prompt, render_prompt

    prompt_data = load_prompt("subprocess_occupation_codegen")
    rendered = render_prompt(prompt_data, occupation="Analyst", task_prompt="...")

    # With experiment YAML overrides:
    rendered = render_prompt(
        prompt_data,
        occupation="Analyst",
        task_prompt="...",
        experiment_prompt={
            "system": "You are a senior analyst.",
            "prefix": "Important context.",
            "body": "Additional instructions.",
            "suffix": "Check your work.",
        },
    )
"""

import yaml
from pathlib import Path
from typing import Dict, Optional


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str = "subprocess_occupation_codegen", prompts_dir: Optional[Path] = None) -> dict:
    """
    Load a prompt template by name.

    Args:
        name: Prompt file name (without .yaml extension)
        prompts_dir: Override prompts directory path

    Returns:
        dict with keys: name, description, system_message, user_prompt

    Raises:
        FileNotFoundError: If prompt file doesn't exist
        ValueError: If required keys are missing
    """
    directory = prompts_dir or PROMPTS_DIR
    prompt_path = directory / f"{name}.yaml"

    if not prompt_path.exists():
        available = [f.stem for f in directory.glob("*.yaml")]
        raise FileNotFoundError(
            f"Prompt '{name}' not found at {prompt_path}. "
            f"Available: {available}"
        )

    with open(prompt_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    required_keys = {"system_message", "user_prompt"}
    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(f"Prompt '{name}' missing required keys: {missing}")

    return data


def render_prompt(
    prompt_data: dict,
    occupation: str = "professional",
    task_prompt: str = "",
    experiment_prompt: Optional[dict] = None,
) -> dict:
    """
    Render prompt template with variables, optionally merging experiment overrides.

    Priority:
        system  = codegen YAML (occupation persona) — always wins
                  experiment YAML system is used ONLY as fallback when codegen has none
        user    = prefix + body + codegen YAML user_prompt (with task_prompt) + suffix

    Args:
        prompt_data: Loaded prompt dict from load_prompt()
        occupation: Professional role
        task_prompt: Task instruction text
        experiment_prompt: Optional dict from experiment YAML condition.prompt
            Keys: system (str), prefix (str|None), body (str|None), suffix (str|None)

    Returns:
        dict with rendered 'system_message' and 'user_prompt'
    """
    variables = {"occupation": occupation, "task_prompt": task_prompt}

    # 1. System: codegen YAML wins (occupation persona).
    #    experiment_prompt["system"] is only used as fallback when codegen has no system_message.
    codegen_system = (prompt_data.get("system_message") or "").strip()
    if codegen_system:
        system_message = codegen_system.format(**variables)
    elif experiment_prompt and experiment_prompt.get("system", "").strip():
        system_message = experiment_prompt["system"].strip()
    else:
        system_message = f"You are a professional {occupation}."

    # 2. User: codegen YAML base + experiment prefix/body/suffix wrapping
    user_prompt = prompt_data["user_prompt"].format(**variables)

    if experiment_prompt:
        # Merge user: prefix → body → [codegen user_prompt] → suffix
        parts = []
        if experiment_prompt.get("prefix"):
            parts.append(experiment_prompt["prefix"].strip())
        if experiment_prompt.get("body"):
            parts.append(experiment_prompt["body"].strip())
        parts.append(user_prompt)
        if experiment_prompt.get("suffix"):
            parts.append(experiment_prompt["suffix"].strip())

        user_prompt = "\n\n".join(parts)

    return {
        "system_message": system_message,
        "user_prompt": user_prompt,
    }


#: Stands in for the task's own words while the wording wrapped around them is
#: measured. One character, taken off again afterwards, so what is reported is
#: what a run place sends about every task rather than what it sends about one.
_TASK_STAND_IN = "t"


def fixed_prompt_characters(
    prompt_data: dict,
    experiment_prompt: Optional[dict] = None,
    occupation: str = "",
) -> Dict[str, int]:
    """What one first request carries besides the task itself, part by part.

    Every figure returned is the length of a string this module really renders,
    through the same :func:`render_prompt` an attempt is built with. Nothing is
    added up from lengths written down a second time, so wording edited in
    ``prompts/<name>.yaml``, a ``prefix``/``body``/``suffix`` added to a run
    place's own settings, or a change to how the two are joined all move this
    with them.

    The parts are measured by difference — the committed prompt file rendered on
    its own, then rendered again with the run place's settings — so they come to
    the whole request exactly. They are kept apart rather than summed here so a
    refusal can say what the total is made of, and so that a run place whose
    ``system`` block loses to the prompt file's own reports nothing for it
    instead of reporting a length that never reaches the model.

    ``occupation`` is formatted into both halves, so a caller pricing a real run
    passes the widest name that run will meet. At its default of ``""`` the
    figures cover the committed wording alone.

    The task's own words are the one thing left out. They are charged per task
    by :func:`core.execution_envelope_cost.max_input_tokens_per_call`, from the
    length recorded for that task, and counting them again here would bill the
    same words twice. What is subtracted is the stand-in that took their place,
    so the wording around them is counted whole.

    Raises whatever :func:`render_prompt` raises when a template will not
    render — a missing key, a stray brace. There is no reading of a template
    nobody can render that would let this return a smaller answer instead.
    """

    def rendered(settings: Optional[dict]) -> tuple:
        parts = render_prompt(
            prompt_data,
            occupation=occupation,
            task_prompt=_TASK_STAND_IN,
            experiment_prompt=settings,
        )
        return len(parts["system_message"]), len(parts["user_prompt"])

    file_system, file_user = rendered(None)
    sent_system, sent_user = rendered(experiment_prompt)

    return {
        "the standing instruction the committed prompt file holds": file_system,
        "the wording the committed prompt file wraps the task in": (
            file_user - len(_TASK_STAND_IN)
        ),
        "the standing instruction this run place's own settings add": (
            sent_system - file_system
        ),
        "the wording this run place's own settings add around it": (
            sent_user - file_user
        ),
    }
