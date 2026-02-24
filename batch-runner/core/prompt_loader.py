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
from typing import Optional


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
