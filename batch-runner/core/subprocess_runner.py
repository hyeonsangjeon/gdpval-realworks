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
import json
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
from core.execution_errors import classify_execution_error
from core.reference_integrity import (
    copy_verified_reference,
    stage_verified_references,
)


# ── Reusable, runner-agnostic helpers (shared with SandboxRunner) ────────────

RUNNER_FILENAME = ".gdpval_runner.py"
PREFLIGHT_PREFIX = "__GDPVAL_PREFLIGHT_V1__"
PREFLIGHT_MAX_LINE_BYTES = 1024


def build_execution_launcher(available_files: list[str]) -> str:
    """Return trusted code that compiles then executes untouched solution.py.

    ``runpy`` injects the historical ``_AVAILABLE_FILES`` and ``os`` globals
    without prepending statements to generated source, so valid ``__future__``
    imports remain at the beginning of ``solution.py``.
    """
    return f'''import json
import os
import runpy
import sys

def emit_preflight(meta):
    sys.stderr.write({PREFLIGHT_PREFIX!r} + json.dumps(meta, separators=(",", ":")) + "\\n")
    sys.stderr.flush()

meta = {{
    "stage": "compile",
    "target_python": ".".join(map(str, sys.version_info[:3])),
}}
with open("solution.py", "r", encoding="utf-8") as source_file:
    source = source_file.read()
try:
    compile(source, "solution.py", "exec", dont_inherit=True)
except SyntaxError as exc:
    meta.update({{
        "ok": False,
        "error_type": type(exc).__name__,
        "line": exc.lineno,
        "offset": exc.offset,
    }})
    emit_preflight(meta)
    raise

meta["ok"] = True
emit_preflight(meta)
runpy.run_path(
    "solution.py",
    run_name="__main__",
    init_globals={{"_AVAILABLE_FILES": {available_files!r}, "os": os}},
)
'''


def _decode_process_output(value: bytes | str | None) -> tuple[str, bool]:
    """Decode process output without allowing binary data to escape handling."""
    if value is None:
        return "", False
    if isinstance(value, str):
        return value, False
    try:
        return value.decode("utf-8"), False
    except UnicodeDecodeError:
        return value.decode("utf-8", errors="replace"), True


def _bounded_preflight(raw) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    ok = raw.get("ok")
    stage = raw.get("stage")
    error_type = raw.get("error_type")
    line = raw.get("line")
    offset = raw.get("offset")
    target_python = raw.get("target_python")
    if not isinstance(ok, bool):
        return None
    if stage != "compile":
        return None
    if error_type is not None and not isinstance(error_type, str):
        return None
    if line is not None and (not isinstance(line, int) or isinstance(line, bool)):
        return None
    if offset is not None and (not isinstance(offset, int) or isinstance(offset, bool)):
        return None
    if not isinstance(target_python, str) or not re.fullmatch(r"\d+\.\d+\.\d+", target_python):
        return None
    return {
        "ok": ok,
        "stage": stage,
        "error_type": error_type,
        "line": line,
        "offset": offset,
        "target_python": target_python,
    }


def parse_execution_streams(
    stdout: bytes | str | None,
    stderr: bytes | str | None,
) -> tuple[str, str, Optional[dict], bool]:
    """Decode output and consume the first launcher-owned protocol record."""
    stdout_text, stdout_decode_error = _decode_process_output(stdout)
    stderr_text, stderr_decode_error = _decode_process_output(stderr)
    preflight = None
    cleaned_lines = []
    consumed = False
    prefix_bytes = PREFLIGHT_PREFIX.encode("ascii")
    for line in stderr_text.splitlines(keepends=True):
        encoded = line.encode("utf-8", errors="replace")
        if not consumed and encoded.startswith(prefix_bytes):
            consumed = True
            if len(encoded) <= PREFLIGHT_MAX_LINE_BYTES:
                payload = line[len(PREFLIGHT_PREFIX):].strip()
                try:
                    preflight = _bounded_preflight(json.loads(payload))
                except (ValueError, TypeError):
                    preflight = None
            continue
        cleaned_lines.append(line)
    return (
        stdout_text,
        "".join(cleaned_lines),
        preflight,
        stdout_decode_error or stderr_decode_error,
    )

def sanitize_code(code: str) -> str:
    """Strip evaluation harness tags that don't belong in executable code."""
    return re.sub(
        r'^\s*CONFIDENCE\s*\[\s*\d+\s*\]\s*$',
        '',
        code,
        flags=re.MULTILINE,
    ).strip()


def extract_code(text: str) -> Optional[str]:
    """Extract Python code from ```python``` fenced blocks (with fallbacks)."""
    pattern = r"```python\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        combined = "\n\n".join(m.strip() for m in matches)
        return sanitize_code(combined)

    # Fallback: fenced block without a language specifier.
    pattern = r"```\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        code = matches[0].strip()
        if "import" in code or "def " in code or "print" in code:
            return sanitize_code(code)

    # Fallback: code block opened but never closed (LLM truncation).
    pattern = r"```python\s*\n(.+)"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        code = match.group(1).strip()
        code = re.sub(r'`{1,3}\s*$', '', code).strip()
        if code:
            return sanitize_code(code)

    return None


def extract_description(text: str) -> str:
    """Return the non-code descriptive text from an LLM response."""
    cleaned = re.sub(r"```[\w]*\s*\n.*?```", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"```[\w]*\s*\n.*$", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


class SubprocessRunner:
    """LLM code generation → safe subprocess execution"""

    #: Whether this run place opens a new request for each turn the model
    #: takes. ``True`` here, though it currently takes only one: ``run`` calls
    #: ``complete`` once, gets the code, and runs it itself. There is no loop,
    #: and if one were ever added it would be a Python loop around that same
    #: call — a fresh request with a fresh cap each time, as in
    #: ``SandboxRunner``.
    #:
    #: Read by core/execution_envelope_preflight.py — see the note on
    #: ``CodeInterpreterRunner.SENDS_A_FRESH_REQUEST_PER_TURN``.
    SENDS_A_FRESH_REQUEST_PER_TURN = True

    #: Which prompt sections this run place fills from the reference files.
    #: All three, built inline in ``run``: ``build_file_structure_info``, then
    #: ``generate_all_previews``, then the "Files available in current
    #: directory" line — see the block at lines 283-299.
    #:
    #: Read by core/execution_envelope_preflight.py — see the note on
    #: ``CodeInterpreterRunner.REFERENCE_FILE_PROMPT_SECTIONS``.
    REFERENCE_FILE_PROMPT_SECTIONS = (
        "file_structure",
        "previews",
        "available_files",
    )

    #: Which prompt sections this run place puts in its **first** request past
    #: the rendered prompt and the reference files. None: ``run`` builds the
    #: three reference-file blocks inline and sends the task, and there is no
    #: deliverable contract, dependency hint or skills manual anywhere in this
    #: module. Empty is a *claim*, not an omission — see the note on
    #: ``CodeInterpreterRunner.FIRST_REQUEST_EXTRA_SECTIONS``.
    FIRST_REQUEST_EXTRA_SECTIONS: tuple[str, ...] = ()

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
        reference_stage = stage_verified_references(reference_files or [])
        reference_stage_entered = False
        try:
            reference_files = reference_stage.__enter__()
            reference_stage_entered = True
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
        finally:
            if reference_stage_entered:
                reference_stage.__exit__(None, None, None)

    def _extract_description(self, text: str) -> str:
        """Extract non-code descriptive text from LLM response.

        Delegates to the module-level :func:`extract_description` (shared with
        SandboxRunner); kept as a method for backward compatibility.
        """
        return extract_description(text)

    def _sanitize_code(self, code: str) -> str:
        """Strip evaluation harness tags that don't belong in executable code."""
        return sanitize_code(code)

    def _extract_code(self, text: str) -> Optional[str]:
        """Extract Python code from ```python``` code blocks.

        Delegates to the module-level :func:`extract_code` (shared with
        SandboxRunner); kept as a method for backward compatibility.
        """
        return extract_code(text)

    def run_code(
        self,
        code: str,
        reference_files: Optional[list] = None,
        skills_dir: Optional[str] = None,
    ) -> dict:
        """Execute already-extracted code in the hardened local sandbox.

        Public wrapper around :meth:`_execute_safely` used by SandboxRunner's
        local fallback so the Docker and local paths share identical security
        controls and (optionally) the mounted ``skills`` package.
        """
        return self._execute_safely(code, reference_files, skills_dir=skills_dir)

    def _execute_safely(
        self,
        code: str,
        reference_files: Optional[list] = None,
        skills_dir: Optional[str] = None,
    ) -> dict:
        """
        Execute code in isolated temporary directory with security controls.

        Args:
            code: Python code to execute
            reference_files: Optional list of file paths to copy
            skills_dir: Optional path to the ``skills`` package. When provided it
                is copied into the execution directory and added to PYTHONPATH so
                generated code can ``from skills import audio, video, ...``.

        Returns:
            dict with success, text, files, error
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                # Keep generated source byte-for-byte intact. A trusted launcher
                # compiles it with the actual target interpreter, then injects
                # harness globals via runpy without breaking __future__ imports.
                code_path = Path(tmpdir) / "solution.py"
                runner_path = Path(tmpdir) / RUNNER_FILENAME

                # Copy reference files to execution directory and track copied files
                copied_files = []
                if reference_files:
                    for src_path in reference_files:
                        copied = copy_verified_reference(src_path, tmpdir)
                        copied_files.append(Path(str(copied)).name)

                # Mount the skills package so generated code can import it
                # (`from skills import audio, video, ...`). Copied into the
                # isolated tmpdir; PYTHONPATH is extended below.
                skills_mounted = False
                if skills_dir and os.path.isdir(skills_dir):
                    try:
                        shutil.copytree(
                            skills_dir,
                            os.path.join(tmpdir, "skills"),
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                        )
                        skills_mounted = True
                    except Exception as e:
                        print(f"Warning: Failed to mount skills package: {e}")

                code_path.write_text(code, encoding="utf-8")
                runner_path.write_text(
                    build_execution_launcher(copied_files),
                    encoding="utf-8",
                )

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

                # Make the mounted skills package importable.
                if skills_mounted:
                    safe_env["PYTHONPATH"] = tmpdir

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
                    [python_executable, str(runner_path)],
                    cwd=tmpdir,
                    env=safe_env,
                    capture_output=True,
                    text=False,
                    timeout=self.timeout,
                    preexec_fn=_set_memory_limit,
                )
                stdout_text, stderr_text, preflight, decode_error = parse_execution_streams(
                    result.stdout,
                    result.stderr,
                )

                # Check for OOM (killed by signal 9 or exit 137)
                if result.returncode == -9 or result.returncode == 137:
                    return {
                        "success": False,
                        "text": stdout_text,
                        "files": [],
                        "preflight": preflight,
                        "error_category": "out_of_memory",
                        "error": f"memory_error: process killed (exit code {result.returncode}, limit {SUBPROCESS_MEMORY_GB}GB)"
                    }

                # Check for MemoryError in stderr
                if result.returncode != 0 and (
                    "MemoryError" in stderr_text
                    or "Cannot allocate memory" in stderr_text
                ):
                    return {
                        "success": False,
                        "text": stdout_text,
                        "files": [],
                        "preflight": preflight,
                        "error_category": "out_of_memory",
                        "error": f"memory_error: {stderr_text[-500:]}"
                    }

                if decode_error:
                    return {
                        "success": False,
                        "text": stdout_text,
                        "files": [],
                        "preflight": preflight,
                        "error_category": "binary_decode_error",
                        "error": "Code execution output was not valid UTF-8 text",
                    }

                # Check execution result
                if result.returncode != 0:
                    return {
                        "success": False,
                        "text": stdout_text,
                        "files": [],
                        "preflight": preflight,
                        "error_category": (
                            classify_execution_error(stderr_text) or "execution_error"
                        ),
                        "error": f"Code execution failed (exit code {result.returncode}):\n{stderr_text}"
                    }

                # Collect generated files (denylist: exclude script + inputs + bytecode)
                output_files = []
                skip_names = {
                    "solution.py",
                    RUNNER_FILENAME,
                } | set(copied_files)
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
                    "text": stdout_text,
                    "files": output_files,
                    "preflight": preflight,
                }

            except subprocess.TimeoutExpired as exc:
                stdout_text, _, preflight, _ = parse_execution_streams(
                    exc.stdout,
                    exc.stderr,
                )
                return {
                    "success": False,
                    "text": stdout_text,
                    "files": [],
                    "preflight": preflight,
                    "error_category": "timeout",
                    "error": f"Code execution timeout ({self.timeout} seconds exceeded)"
                }

            except UnicodeDecodeError:
                return {
                    "success": False,
                    "text": "",
                    "files": [],
                    "preflight": None,
                    "error_category": "binary_decode_error",
                    "error": "Code execution output was not valid UTF-8 text",
                }

            except Exception as e:
                return {
                    "success": False,
                    "text": "",
                    "files": [],
                    "preflight": None,
                    "error_category": classify_execution_error(str(e)),
                    "error": f"Execution error: {str(e)}"
                }
