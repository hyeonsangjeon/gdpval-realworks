"""
Task Executor - Mode dispatcher for file generation.

Selects and delegates to appropriate runner based on execution mode:
- code_interpreter: Azure OpenAI Responses API (OpenAI models only)
- subprocess: LLM code generation + safe execution (all models)
- json_renderer: JSON spec + fixed renderer (fair comparison mode)
"""

from typing import Literal, Optional

from core.code_interpreter import CodeInterpreterRunner
from core.subprocess_runner import SubprocessRunner
from core.json_renderer import JsonRenderer

# Execution modes
ExecutionMode = Literal["code_interpreter", "subprocess", "json_renderer"]


class TaskExecutor:
    """Task executor that dispatches to appropriate runner based on mode"""

    def __init__(
        self,
        mode: ExecutionMode,
        llm_client=None,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        prompt_name: Optional[str] = None
    ):
        """
        Initialize executor with specified mode.

        Args:
            mode: Execution mode (code_interpreter, subprocess, json_renderer)
            llm_client: AzureOpenAI client (required for subprocess and json_renderer)
            api_key: Azure OpenAI API key (optional, for code_interpreter)
            endpoint: Azure OpenAI endpoint (optional, for code_interpreter)
            prompt_name: Prompt YAML name for subprocess mode (default: subprocess_occupation_codegen)

        Raises:
            ValueError: If required parameters are missing for the selected mode
        """
        self.mode = mode

        if mode == "code_interpreter":
            # Code Interpreter uses its own client
            self.runner = CodeInterpreterRunner(
                api_key=api_key,
                endpoint=endpoint,
                prompt_name=prompt_name,
            )

        elif mode == "subprocess":
            if llm_client is None:
                raise ValueError("subprocess mode requires llm_client")
            self.runner = SubprocessRunner(
                llm_client,
                prompt_name=prompt_name or SubprocessRunner.DEFAULT_PROMPT,
            )

        elif mode == "json_renderer":
            if llm_client is None:
                raise ValueError("json_renderer mode requires llm_client")
            self.runner = JsonRenderer(llm_client)

        else:
            raise ValueError(f"Unknown execution mode: {mode}")

    def execute(
        self,
        task_prompt: str,
        model: str,
        reference_files: Optional[list] = None,
        occupation: str = "professional",
        experiment_prompt: Optional[dict] = None,
        verbose: bool = False,
    ) -> dict:
        """
        Execute task using selected runner.

        Args:
            task_prompt: The task instruction
            model: Model deployment name
            reference_files: Optional list of reference file paths
            occupation: Professional role from task data
            experiment_prompt: Optional prompt overrides from experiment YAML
                Keys: system (str), prefix (str|None), body (str|None), suffix (str|None)
            verbose: Print detailed debug info (code_interpreter mode only)

        Returns:
            dict with standardized format:
                - success (bool): Whether execution succeeded
                - text (str): Text response
                - files (list): Generated files [{filename, content}]
                - error (str, optional): Error message if failed
        """
        try:
            if self.mode == "code_interpreter":
                return self.runner.run(
                    task_prompt=task_prompt,
                    model=model,
                    reference_files=reference_files,
                    occupation=occupation,
                    experiment_prompt=experiment_prompt,
                    verbose=verbose,
                )

            elif self.mode == "subprocess":
                return self.runner.run(
                    task_prompt=task_prompt,
                    model=model,
                    reference_files=reference_files,
                    occupation=occupation,
                    experiment_prompt=experiment_prompt,
                )

            elif self.mode == "json_renderer":
                # JSON renderer doesn't use reference files (spec only)
                return self.runner.run(
                    task_prompt=task_prompt,
                    model=model
                )

        except Exception as e:
            return {
                "success": False,
                "text": "",
                "files": [],
                "error": f"Executor error ({self.mode}): {str(e)}"
            }

    @staticmethod
    def validate_mode(mode: str, model_provider: str) -> tuple[bool, Optional[str]]:
        """
        Validate if execution mode is compatible with model provider.

        Args:
            mode: Execution mode
            model_provider: Model provider (e.g., "azure", "openai", "anthropic")

        Returns:
            (is_valid, error_message) tuple
        """
        if mode == "code_interpreter":
            # Code Interpreter only works with OpenAI/Azure OpenAI
            if model_provider not in ["azure", "openai"]:
                return (
                    False,
                    f"code_interpreter mode requires OpenAI/Azure OpenAI, got {model_provider}"
                )

        return (True, None)

    @staticmethod
    def recommend_mode(model_provider: str, score_type: str = "tool_assisted") -> ExecutionMode:
        """
        Recommend execution mode based on model provider and score type.

        Args:
            model_provider: Model provider (e.g., "azure", "openai", "anthropic")
            score_type: Score type ("tool_assisted" or "portable")

        Returns:
            Recommended ExecutionMode
        """
        # Fair comparison mode: always use JSON renderer
        if score_type == "portable":
            return "json_renderer"

        # Tool-assisted mode: use best available for each provider
        if model_provider in ["azure", "openai"]:
            return "code_interpreter"
        else:
            return "subprocess"
