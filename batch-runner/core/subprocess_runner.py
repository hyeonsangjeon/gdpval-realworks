"""
Subprocess Runner for non-OpenAI models.

Generates Python code using LLM, then executes it safely in an isolated subprocess
environment with strict security controls.

Security features:
- Isolated temporary directory
- Environment variable whitelist (no API keys)
- Configurable timeout (see config.SUBPROCESS_TIMEOUT)
- No network access (subprocess has no credentials)
"""

import subprocess
import tempfile
import shutil
import os
import re
import resource
import sys
from pathlib import Path
from typing import Optional

from core.config import SUBPROCESS_TIMEOUT, SUBPROCESS_MEMORY_GB, DEFAULT_TOKENS
from core.llm_client import complete
from core.prompt_loader import load_prompt, render_prompt
from core.file_preview import generate_all_previews, build_file_structure_info


class SubprocessRunner:
    """LLM code generation → safe subprocess execution"""

    DEFAULT_PROMPT = "subprocess_occupation_codegen"

    def __init__(
        self,
        llm_client,
        prompt_name: str = DEFAULT_PROMPT,
        max_completion_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
    ):
        """
        Initialize Subprocess runner with LLM client.

        Args:
            llm_client: AzureOpenAI client instance for code generation
            prompt_name: Name of prompt YAML file in prompts/ (without .yaml)
            max_completion_tokens: Completion token cap override
            timeout: Subprocess timeout override in seconds (default: SUBPROCESS_TIMEOUT)
            reasoning_effort: Optional reasoning effort level ("low", "medium", "high")
        """
        self.llm_client = llm_client
        self.prompt_name = prompt_name
        self.prompt_data = load_prompt(prompt_name)
        self.max_completion_tokens = (
            max_completion_tokens
            if max_completion_tokens is not None
            else DEFAULT_TOKENS["code_generation"]
        )
        self.timeout = timeout or SUBPROCESS_TIMEOUT
        self.reasoning_effort = reasoning_effort

    def run(
        self,
        task_prompt: str,
        model: str,
        reference_files: Optional[list] = None,
        occupation: str = "professional",
        experiment_prompt: Optional[dict] = None,
    ) -> dict:
        """
        Generate code via LLM and execute safely in subprocess.

        Args:
            task_prompt: The task instruction
            model: Model deployment name
            reference_files: Optional list of file paths to copy to execution dir
            occupation: Professional role from task data
            experiment_prompt: Optional prompt overrides from experiment YAML
                Keys: system (str), prefix (str|None), body (str|None), suffix (str|None)

        Returns:
            dict with keys:
                - success (bool): Whether execution succeeded
                - text (str): stdout from code execution
                - files (list): List of generated files [{filename, content}]
                - error (str, optional): Error message if failed
        """
        try:
            # Reference 파일 구조 자동 주입 (컬럼명 하드코딩 에러 방지)
            file_structure_info = build_file_structure_info(reference_files or [])
            if file_structure_info:
                task_prompt = file_structure_info + "\n\n" + task_prompt

            # Step 0: Generate reference file previews and append to task_prompt
            if reference_files:
                previews = generate_all_previews(reference_files)
                if previews:
                    task_prompt = task_prompt + "\n\n" + previews

                # Explicitly list available files for LLM code generation
                available_files = [os.path.basename(f) for f in reference_files]
                task_prompt = (
                    task_prompt
                    + f"\n\n📁 Files available in current directory (you can use them directly): {available_files}"
                )

            # Step 1: Generate code using LLM
            rendered = render_prompt(
                self.prompt_data,
                occupation=occupation,
                task_prompt=task_prompt,
                experiment_prompt=experiment_prompt,
            )

            messages = [
                {"role": "system", "content": rendered["system_message"]},
                {"role": "user", "content": rendered["user_prompt"]}
            ]

            response, _ = complete(
                client=self.llm_client,
                model=model,
                messages=messages,
                max_completion_tokens=self.max_completion_tokens,
                reasoning_effort=self.reasoning_effort,
            )

            response_text = response.choices[0].message.content

            # Step 2: Extract code and description from response
            code = self._extract_code(response_text)
            if not code:
                return {
                    "success": False,
                    "text": "",
                    "deliverable_text": "",
                    "files": [],
                    "error": f"No Python code found in LLM response. Response: {response_text[:200]}..."
                }

            # Extract the descriptive text (non-code portion of LLM response)
            deliverable_text = self._extract_description(response_text)

            # Step 3: Execute safely in isolated environment
            result = self._execute_safely(code, reference_files)
            result["deliverable_text"] = deliverable_text
            return result

        except Exception as e:
            return {
                "success": False,
                "text": "",
                "files": [],
                "error": f"Code generation failed: {str(e)}"
            }

    def _extract_description(self, text: str) -> str:
        """Extract non-code descriptive text from LLM response.

        Strips code blocks and returns the remaining text as a
        meta description of what deliverables were created.

        Args:
            text: Full LLM response text

        Returns:
            Descriptive text with code blocks removed
        """
        # Remove all closed code blocks (```python...``` or ```...```)
        cleaned = re.sub(r"```[\w]*\s*\n.*?```", "", text, flags=re.DOTALL)
        # Remove unclosed code blocks (LLM truncation or trailing code)
        cleaned = re.sub(r"```[\w]*\s*\n.*$", "", cleaned, flags=re.DOTALL)
        # Clean up excessive whitespace
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned

    def _sanitize_code(self, code: str) -> str:
        """Strip evaluation harness tags that don't belong in executable code."""
        return re.sub(
            r'^\s*CONFIDENCE\s*\[\s*\d+\s*\]\s*$',
            '',
            code,
            flags=re.MULTILINE,
        ).strip()

    def _extract_code(self, text: str) -> Optional[str]:
        """
        Extract Python code from ```python``` code blocks.

        Args:
            text: LLM response text

        Returns:
            Extracted code or None if not found
        """
        # Pattern: ```python ... ``` (flexible whitespace)
        pattern = r"```python\s*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)

        if matches:
            # Concatenate all code blocks if multiple
            combined = "\n\n".join(m.strip() for m in matches)
            return self._sanitize_code(combined)

        # Fallback: Try without language specifier
        pattern = r"```\s*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)

        if matches:
            # Check if it looks like Python code
            code = matches[0].strip()
            if "import" in code or "def " in code or "print" in code:
                return self._sanitize_code(code)

        # Fallback: Code block opened but never closed (LLM truncation)
        pattern = r"```python\s*\n(.+)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            code = match.group(1).strip()
            # Remove trailing ``` if partially present
            code = re.sub(r'`{1,3}\s*$', '', code).strip()
            if code:
                return self._sanitize_code(code)

        return None

    def _execute_safely(
        self,
        code: str,
        reference_files: Optional[list] = None
    ) -> dict:
        """
        Execute code in isolated temporary directory with security controls.

        Args:
            code: Python code to execute
            reference_files: Optional list of file paths to copy

        Returns:
            dict with success, text, files, error
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                # Path of the script the subprocess will execute. Actual write
                # happens after the _AVAILABLE_FILES header is prepended below
                # so the persisted file matches the in-memory `code`.
                code_path = Path(tmpdir) / "solution.py"

                # Copy reference files to execution directory and track copied files
                copied_files = []
                if reference_files:
                    for src_path in reference_files:
                        if os.path.exists(src_path):
                            try:
                                filename = os.path.basename(src_path)
                                shutil.copy(src_path, tmpdir)
                                copied_files.append(filename)
                            except Exception as e:
                                print(f"Warning: Failed to copy reference file {src_path}: {e}")

                # Inject available files list as runtime info (top of code)
                if copied_files:
                    files_header = (
                        "import os\n"
                        f"_AVAILABLE_FILES = {copied_files}\n"
                        f"# Available files: {', '.join(copied_files)}\n\n"
                    )
                    code = files_header + code
                else:
                    code = "# No reference files available\n\n" + code

                # Persist the (possibly header-prepended) code so the subprocess
                # actually executes the version with the _AVAILABLE_FILES hint.
                code_path.write_text(code, encoding="utf-8")

                # 🔒 Security: Whitelist environment variables
                # Use current Python's PATH so venv packages are available
                # but strip API keys and secrets
                safe_env = {
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
                    "LANG": "C.UTF-8",
                    "HOME": tmpdir,
                    "TMPDIR": tmpdir,
                    # LibreOffice headless 모드에 필요
                    "XDG_CONFIG_HOME": tmpdir,
                    "XDG_CACHE_HOME": tmpdir,
                    # 폰트 접근용
                    "FONTCONFIG_PATH": "/etc/fonts",
                    # Explicitly NO: AZURE_OPENAI_API_KEY, HF_TOKEN, etc.
                }

                # Preserve VIRTUAL_ENV and related paths for package access
                if "VIRTUAL_ENV" in os.environ:
                    safe_env["VIRTUAL_ENV"] = os.environ["VIRTUAL_ENV"]

                # Use the same Python interpreter (preserves venv)
                python_executable = sys.executable

                def _set_memory_limit():
                    """Limit subprocess virtual address space to prevent runner OOM.

                    Default 5GB, configurable via SUBPROCESS_MEMORY_GB env var.
                    GitHub Actions ubuntu-latest has 7GB RAM; parent process uses
                    ~0.5-0.8GB, OS ~1-1.5GB, leaving ~4.7-5.5GB for the child.

                    RLIMIT_AS is Linux-only. On macOS/Windows this is a no-op
                    (memory runs uncapped on local dev machines).
                    """
                    try:
                        limit_bytes = SUBPROCESS_MEMORY_GB * 1024**3
                        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
                    except (ValueError, OSError):
                        pass  # RLIMIT_AS not available (macOS, Windows, etc.)

                # Execute code with timeout
                result = subprocess.run(
                    [python_executable, str(code_path)],
                    cwd=tmpdir,
                    env=safe_env,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    preexec_fn=_set_memory_limit,
                )

                # Check for OOM (killed by signal 9 or exit 137)
                if result.returncode == -9 or result.returncode == 137:
                    return {
                        "success": False,
                        "text": result.stdout,
                        "files": [],
                        "error": f"memory_error: process killed (exit code {result.returncode}, limit {SUBPROCESS_MEMORY_GB}GB)"
                    }

                # Check for MemoryError in stderr
                if result.returncode != 0 and (
                    "MemoryError" in result.stderr
                    or "Cannot allocate memory" in result.stderr
                ):
                    return {
                        "success": False,
                        "text": result.stdout,
                        "files": [],
                        "error": f"memory_error: {result.stderr[-500:]}"
                    }

                # Check execution result
                if result.returncode != 0:
                    return {
                        "success": False,
                        "text": result.stdout,
                        "files": [],
                        "error": f"Code execution failed (exit code {result.returncode}):\n{result.stderr}"
                    }

                # Collect generated files (denylist: exclude script + inputs + bytecode)
                output_files = []
                skip_names = {"solution.py"} | set(copied_files)
                skip_suffixes = {".pyc"}

                for file_path in Path(tmpdir).iterdir():
                    # Skip directories (__pycache__, etc.)
                    if file_path.is_dir():
                        continue
                    # Skip the solution script and reference input files
                    if file_path.name in skip_names:
                        continue
                    # Skip Python bytecode
                    if file_path.suffix in skip_suffixes:
                        continue

                    try:
                        # Sanitize filename: replace NTFS-forbidden chars
                        # (: " < > | * ? \r \n) with underscore.
                        # LLM-generated filenames may contain these, causing
                        # actions/upload-artifact failures on Windows/CI.
                        safe_name = re.sub(r'[:"<>|*?\r\n]', '_', file_path.name)
                        output_files.append({
                            "filename": safe_name,
                            "content": file_path.read_bytes()
                        })
                    except Exception as e:
                        print(f"Warning: Failed to read generated file {file_path}: {e}")

                return {
                    "success": True,
                    "text": result.stdout,
                    "files": output_files
                }

            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "text": "",
                    "files": [],
                    "error": f"Code execution timeout ({self.timeout} seconds exceeded)"
                }

            except Exception as e:
                return {
                    "success": False,
                    "text": "",
                    "files": [],
                    "error": f"Execution error: {str(e)}"
                }
