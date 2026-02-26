"""GDPVal RealWork — Central Configuration

All project-wide constants and hardcoded values live here.
Every module should import from this file instead of defining its own.

Usage:
    from core.config import DATASET_ID, EXPECTED_SECTORS, PROMPT_PRESETS
"""

from pathlib import Path
from dataclasses import dataclass
from typing import Optional


# ─── Paths ────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # gdpval-realwork/
BATCH_RUNNER_ROOT = Path(__file__).resolve().parent.parent     # batch-runner/

DEFAULT_LOCAL_PATH = PROJECT_ROOT / "data" / "gdpval-local"
WORKSPACE_DIR = BATCH_RUNNER_ROOT / "workspace"       # intermediate artifacts
UPLOAD_DIR = WORKSPACE_DIR / "upload"                  # HF upload staging area
DELIVERABLE_DIR = UPLOAD_DIR / "deliverable_files"     # generated files (step2 output)
BATCH_OUTPUT_DIR = PROJECT_ROOT / "batch-output"

# HF dataset snapshot validation markers
# Arrow format (save_to_disk) or raw HF snapshot (snapshot_download)
SNAPSHOT_MARKERS = ("dataset_dict.json", "dataset_info.json", "data")


# ─── HuggingFace ──────────────────────────────────────────────────────────

DATASET_ID = "openai/gdpval"
HF_RESULTS_REPO_ID = "gdpval-realworks"
HF_DATASET_URI_PREFIX = f"hf://datasets/{DATASET_ID}@main"


# ─── Dataset Schema ───────────────────────────────────────────────────────

EXPECTED_TASK_COUNT = 220
EXPECTED_SECTOR_COUNT = 9

EXPECTED_SECTORS = {
    "Professional, Scientific, and Technical Services",
    "Government",
    "Information",
    "Manufacturing",
    "Real Estate and Rental and Leasing",
    "Finance and Insurance",
    "Wholesale Trade",
    "Health Care and Social Assistance",
    "Retail Trade",
}

EXPECTED_SECTOR_DISTRIBUTION = {
    "Professional, Scientific, and Technical Services": 25,
    "Government": 25,
    "Information": 25,
    "Manufacturing": 25,
    "Real Estate and Rental and Leasing": 25,
    "Finance and Insurance": 25,
    "Wholesale Trade": 25,
    "Health Care and Social Assistance": 25,
    "Retail Trade": 20,
}


# ─── Prompt Presets ────────────────────────────────────────────────────────

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."

@dataclass
class PromptPreset:
    """Configuration for a prompt strategy"""
    name: str
    system_prompt: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None

PROMPT_PRESETS = {
    "baseline": PromptPreset(
        name="baseline",
        system_prompt=DEFAULT_SYSTEM_PROMPT,
    ),
    "visual_inspection": PromptPreset(
        name="visual_inspection",
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        suffix=(
            "\nSTEP 1: Convert all visual deliverables to PNGs using LibreOffice."
            "\nSTEP 2: Display the PNGs. Look at each image thoroughly, zoom in if needed."
            "\nSTEP 3: Verify your output matches the requirements before submitting."
        ),
    ),
    "reasoning_high": PromptPreset(
        name="reasoning_high",
        system_prompt=f"{DEFAULT_SYSTEM_PROMPT} Think step by step carefully.",
    ),
    "reasoning_low": PromptPreset(
        name="reasoning_low",
        system_prompt=DEFAULT_SYSTEM_PROMPT,
    ),
    "cot": PromptPreset(
        name="cot",
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        suffix="\n\nLet's think step by step.",
    ),
}


# ─── Batch Pipeline ───────────────────────────────────────────────────────

SUBPROCESS_TIMEOUT = 570  # subprocess mode: max seconds per code execution (9min 30s)

# Azure AI 모델 (모두 AzureOpenAI SDK로 호출)
SUPPORTED_MODELS = [
    "gpt-5.2-chat",       # Azure OpenAI — GPT-5.2
    "gpt-4o",             # Azure OpenAI — GPT-4o
    "grok-3",             # Azure AI — xAI Grok-3
    "claude-3.5-sonnet",  # Azure AI — Anthropic Claude
]

DEFAULT_MODEL = "gpt-5.2-chat"
DEFAULT_DEPLOYMENT = "gpt-5.2-chat"
DEFAULT_ENDPOINT = "https://dlstmvprtus-wingnut0310-ai.openai.azure.com/"
DEFAULT_API_VERSION = "2025-04-01-preview"
DEFAULT_MAX_COMPLETION_TOKENS = 16384
