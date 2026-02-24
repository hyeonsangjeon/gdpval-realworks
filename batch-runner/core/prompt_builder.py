"""Prompt Builder for GDPVal Experiments

Builds prompts with different experimental conditions (baseline, visual inspection, reasoning, etc.)
"""

from typing import Dict, Any, Optional
from .data_loader import GDPValTask
from .config import PROMPT_PRESETS, PromptPreset
from .file_reader import read_all_references

# Re-export for backward compatibility
PromptConfig = PromptPreset


class PromptBuilder:
    """실험 조건별 프롬프트 빌더"""

    PRESETS: Dict[str, PromptPreset] = PROMPT_PRESETS

    def __init__(
        self,
        config: PromptConfig,
        reference_base_dir: Optional[str] = None,
        max_chars_per_file: int = 50_000,
    ):
        self.config = config
        self.reference_base_dir = reference_base_dir
        self.max_chars_per_file = max_chars_per_file

    @classmethod
    def from_preset(
        cls,
        preset_name: str,
        reference_base_dir: Optional[str] = None,
    ) -> 'PromptBuilder':
        """Create a PromptBuilder from a preset name

        Args:
            preset_name: Name of the preset (baseline, visual_inspection, etc.)
            reference_base_dir: Base directory for reference files

        Returns:
            PromptBuilder instance

        Raises:
            ValueError: If preset_name is not found
        """
        if preset_name not in cls.PRESETS:
            available = ", ".join(cls.PRESETS.keys())
            raise ValueError(
                f"Unknown preset: '{preset_name}'. "
                f"Available presets: {available}"
            )
        return cls(
            cls.PRESETS[preset_name],
            reference_base_dir=reference_base_dir,
        )

    @classmethod
    def get_preset_names(cls) -> list[str]:
        """Get list of available preset names"""
        return list(cls.PRESETS.keys())

    def build(self, task: GDPValTask) -> Dict[str, Any]:
        """Build a prompt from a task

        Args:
            task: GDPValTask to build prompt from

        Returns:
            Dictionary with 'system', 'user', and 'metadata' keys
        """
        user_prompt = task.prompt

        if self.config.prefix:
            user_prompt = self.config.prefix + "\n" + user_prompt

        if self.config.suffix:
            user_prompt = user_prompt + "\n" + self.config.suffix

        # Append reference file contents
        if task.reference_files:
            ref_content = read_all_references(
                task,
                base_dir=self.reference_base_dir,
                max_chars_per_file=self.max_chars_per_file,
            )
            if ref_content:
                user_prompt = (
                    user_prompt
                    + "\n\n=== Reference Files ===\n"
                    + ref_content
                )

        return {
            "system": self.config.system_prompt,
            "user": user_prompt,
            "metadata": {
                "task_id": task.task_id,
                "prompt_config": self.config.name,
                "sector": task.sector,
                "occupation": task.occupation,
            }
        }

    def build_batch(self, tasks: list[GDPValTask]) -> list[Dict[str, Any]]:
        """Build prompts for multiple tasks

        Args:
            tasks: List of GDPValTasks

        Returns:
            List of prompt dictionaries
        """
        return [self.build(task) for task in tasks]

    def __repr__(self) -> str:
        return f"PromptBuilder(config={self.config.name})"
