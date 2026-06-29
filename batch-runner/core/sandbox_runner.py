"""Sandbox Runner — containerized, skill-aware evolution of subprocess mode.

This is the "new testing method" for GDPVal solving:

* **Container sandbox** — LLM-generated ``solution.py`` runs inside a Docker
  container (``--network none``, memory/CPU/PID caps) built from the project
  ``requirements.txt`` plus system tools (ffmpeg, libreoffice, tesseract,
  poppler). When the Docker daemon or image is unavailable (e.g. local dev) it
  gracefully falls back to the hardened in-process subprocess sandbox.
* **Per-task dependency discovery** — :mod:`core.dependency_resolver` derives the
  pip packages each task needs from reference-file extensions, task keywords, and
  the generated code's imports, and flags anything missing from the base image.
* **Skills** — :mod:`core.skills_registry` selects the famous-library Agent
  Skills relevant to the task (audio/video/document/image/data). Their manuals
  are injected into the prompt and the ``skills`` package is mounted into the
  sandbox, giving generated code *vision* (video frame-by-frame, image OCR) and
  *hearing* (audio FFT / sampling / loudness).

The public surface mirrors :class:`core.subprocess_runner.SubprocessRunner` so
:class:`core.executor.TaskExecutor` can dispatch to it interchangeably.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from core.config import SUBPROCESS_TIMEOUT, SUBPROCESS_MEMORY_GB, DEFAULT_TOKENS
from core.dependency_resolver import DependencyManifest, load_base_packages, resolve
from core.file_preview import build_file_structure_info, generate_all_previews
from core.llm_client import complete
from core.prompt_loader import load_prompt, render_prompt
from core.skills_registry import SkillsRegistry
from core.subprocess_runner import SubprocessRunner, extract_code, extract_description

DEFAULT_SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "gdpval-sandbox:latest")

# Cache for the (relatively expensive) `docker info` probe.
_DOCKER_AVAILABLE: Optional[bool] = None


def docker_available(refresh: bool = False) -> bool:
    """Return True if a Docker CLI + responsive daemon are present (cached)."""
    global _DOCKER_AVAILABLE
    if _DOCKER_AVAILABLE is not None and not refresh:
        return _DOCKER_AVAILABLE
    available = False
    if shutil.which("docker"):
        try:
            proc = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            available = proc.returncode == 0
        except Exception:
            available = False
    _DOCKER_AVAILABLE = available
    return available


def docker_image_exists(image: str) -> bool:
    """Return True if the sandbox image is present locally."""
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0
    except Exception:
        return False


class SandboxRunner:
    """LLM code generation → skill-aware, containerized execution."""

    DEFAULT_PROMPT = "sandbox_occupation_codegen"

    def __init__(
        self,
        llm_client,
        prompt_name: str = DEFAULT_PROMPT,
        max_completion_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
        skills_dir: Optional[str] = None,
        image: Optional[str] = None,
        use_docker: str = "auto",          # "auto" | "never" | "always"
        memory_gb: Optional[int] = None,
        cpus: Optional[float] = None,
        max_skills: int = 5,
    ):
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
        self.image = image or DEFAULT_SANDBOX_IMAGE
        self.use_docker = use_docker
        self.memory_gb = memory_gb or SUBPROCESS_MEMORY_GB
        self.cpus = cpus
        self.max_skills = max_skills

        self.registry = SkillsRegistry(skills_dir)
        self.skills_dir = str(self.registry.skills_dir)
        self._base_packages = load_base_packages()
        # Reused for local fallback execution (shares hardened security path).
        self._local = SubprocessRunner(
            llm_client,
            prompt_name=SubprocessRunner.DEFAULT_PROMPT,
            timeout=self.timeout,
        )

    # ── public API ───────────────────────────────────────────────────────
    def run(
        self,
        task_prompt: str,
        model: str,
        reference_files: Optional[list] = None,
        occupation: str = "professional",
        experiment_prompt: Optional[dict] = None,
    ) -> dict:
        """Generate code with skill/dependency context and run it in the sandbox."""
        try:
            ref_files = reference_files or []

            # 1) Perception context: select skills + resolve dependencies.
            skills = self.registry.select(ref_files, task_prompt, max_skills=self.max_skills)
            manifest = resolve(
                reference_files=ref_files,
                task_text=task_prompt,
                base_packages=self._base_packages,
            )

            # 2) Build the augmented task prompt and generate code.
            augmented = self._augment_prompt(task_prompt, ref_files, skills, manifest)
            rendered = render_prompt(
                self.prompt_data,
                occupation=occupation,
                task_prompt=augmented,
                experiment_prompt=experiment_prompt,
            )
            messages = [
                {"role": "system", "content": rendered["system_message"]},
                {"role": "user", "content": rendered["user_prompt"]},
            ]
            response, _ = complete(
                client=self.llm_client,
                model=model,
                messages=messages,
                max_completion_tokens=self.max_completion_tokens,
                reasoning_effort=self.reasoning_effort,
            )
            response_text = response.choices[0].message.content
            code = extract_code(response_text)
            if not code:
                return {
                    "success": False,
                    "text": "",
                    "deliverable_text": "",
                    "files": [],
                    "error": f"No Python code found in LLM response. Response: {response_text[:200]}...",
                    "metadata": self._metadata("none", skills, manifest),
                }
            deliverable_text = extract_description(response_text)

            # Re-resolve including the code's imports (better missing-dep signal).
            manifest = resolve(
                reference_files=ref_files,
                task_text=task_prompt,
                code=code,
                base_packages=self._base_packages,
            )

            # 3) Execute (Docker when possible, else local fallback).
            executor_used, result = self._execute(code, ref_files, manifest)
            result["deliverable_text"] = deliverable_text
            result["metadata"] = self._metadata(executor_used, skills, manifest)
            return result

        except Exception as e:  # pragma: no cover - defensive
            return {
                "success": False,
                "text": "",
                "files": [],
                "error": f"Sandbox code generation failed: {str(e)}",
            }

    # ── prompt augmentation ──────────────────────────────────────────────
    def _augment_prompt(
        self,
        task_prompt: str,
        reference_files: List[str],
        skills,
        manifest: DependencyManifest,
    ) -> str:
        parts: List[str] = []

        file_structure_info = build_file_structure_info(reference_files or [])
        if file_structure_info:
            parts.append(file_structure_info)

        skills_manual = self.registry.render_manual(skills)
        if skills_manual:
            parts.append(skills_manual)

        dep_hint = manifest.to_prompt_hint()
        if dep_hint:
            parts.append(dep_hint)

        parts.append(task_prompt)

        if reference_files:
            previews = generate_all_previews(reference_files)
            if previews:
                parts.append(previews)
            available_files = [os.path.basename(f) for f in reference_files]
            parts.append(
                f"📁 Files available in the sandbox working directory "
                f"(use them directly): {available_files}"
            )

        return "\n\n".join(parts)

    def _metadata(self, executor_used: str, skills, manifest: DependencyManifest) -> dict:
        return {
            "executor": executor_used,
            "image": self.image if executor_used == "docker" else None,
            "skills": [s.name for s in skills],
            "skills_detail": [s.to_dict() for s in skills],
            "dependencies": manifest.to_dict(),
        }

    # ── execution dispatch ───────────────────────────────────────────────
    def _execute(
        self,
        code: str,
        reference_files: List[str],
        manifest: DependencyManifest,
    ) -> Tuple[str, dict]:
        if self.use_docker == "never":
            return "local", self._local.run_code(code, reference_files, skills_dir=self.skills_dir)

        if docker_available():
            if docker_image_exists(self.image):
                return "docker", self._execute_docker(code, reference_files)
            if self.use_docker == "always":
                return "docker", {
                    "success": False,
                    "text": "",
                    "files": [],
                    "error": f"Sandbox image '{self.image}' not found. Build it: "
                             f"bash sandbox/build.sh",
                }
            print(f"      ⚠️  Sandbox image '{self.image}' missing — falling back to local execution")
        elif self.use_docker == "always":
            return "docker", {
                "success": False,
                "text": "",
                "files": [],
                "error": "Docker daemon unavailable but use_docker='always'.",
            }
        else:
            print("      ⚠️  Docker unavailable — falling back to hardened local execution")

        return "local", self._local.run_code(code, reference_files, skills_dir=self.skills_dir)

    # ── Docker execution ─────────────────────────────────────────────────
    def _execute_docker(self, code: str, reference_files: Optional[list]) -> dict:
        """Run generated code inside the sandbox container."""
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                # Copy reference files into the bind-mounted workdir.
                copied_files: List[str] = []
                for src_path in reference_files or []:
                    if os.path.exists(src_path):
                        try:
                            shutil.copy(src_path, tmpdir)
                            copied_files.append(os.path.basename(src_path))
                        except Exception as e:
                            print(f"Warning: failed to copy reference file {src_path}: {e}")

                # Mount the skills package.
                skills_mounted = False
                if self.skills_dir and os.path.isdir(self.skills_dir):
                    try:
                        shutil.copytree(
                            self.skills_dir,
                            os.path.join(tmpdir, "skills"),
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                        )
                        skills_mounted = True
                    except Exception as e:
                        print(f"Warning: failed to mount skills package: {e}")

                # Prepend the available-files hint (mirrors subprocess mode).
                if copied_files:
                    header = (
                        "import os\n"
                        f"_AVAILABLE_FILES = {copied_files}\n"
                        f"# Available files: {', '.join(copied_files)}\n\n"
                    )
                    code = header + code
                else:
                    code = "# No reference files available\n\n" + code
                (Path(tmpdir) / "solution.py").write_text(code, encoding="utf-8")

                cmd = self._docker_command(tmpdir, skills_mounted)
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout + 30,  # allow container start overhead
                )

                if result.returncode in (137, -9):
                    return {
                        "success": False,
                        "text": result.stdout,
                        "files": [],
                        "error": f"memory_error: container killed "
                                 f"(exit {result.returncode}, limit {self.memory_gb}GB)",
                    }
                if result.returncode != 0:
                    return {
                        "success": False,
                        "text": result.stdout,
                        "files": [],
                        "error": f"Sandbox execution failed (exit {result.returncode}):\n{result.stderr[-1500:]}",
                    }

                return {
                    "success": True,
                    "text": result.stdout,
                    "files": self._collect_output_files(tmpdir, copied_files),
                }

            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "text": "",
                    "files": [],
                    "error": f"Sandbox execution timeout ({self.timeout}s exceeded)",
                }
            except Exception as e:
                return {
                    "success": False,
                    "text": "",
                    "files": [],
                    "error": f"Sandbox execution error: {str(e)}",
                }

    def _docker_command(self, workdir: str, skills_mounted: bool) -> List[str]:
        # Baked-in skills live at /opt/gdpval; mounted skills (if any) at /work.
        pythonpath = "/work:/opt/gdpval" if skills_mounted else "/opt/gdpval"
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", f"{self.memory_gb}g",
            "--memory-swap", f"{self.memory_gb}g",
            "--pids-limit", "512",
            "--security-opt", "no-new-privileges",
            "-v", f"{workdir}:/work:rw",
            "-w", "/work",
            "-e", "HOME=/work",
            "-e", "LANG=C.UTF-8",
            "-e", f"PYTHONPATH={pythonpath}",
        ]
        if self.cpus:
            cmd += ["--cpus", str(self.cpus)]
        cmd += [self.image, "python", "-u", "solution.py"]
        return cmd

    @staticmethod
    def _collect_output_files(workdir: str, copied_files: List[str]) -> list:
        """Collect generated files (exclude script, inputs, skills, bytecode)."""
        output_files = []
        skip_names = {"solution.py"} | set(copied_files)
        for file_path in Path(workdir).iterdir():
            if file_path.is_dir():           # skip skills/, __pycache__, etc.
                continue
            if file_path.name in skip_names:
                continue
            if file_path.suffix == ".pyc":
                continue
            try:
                safe_name = re.sub(r'[:"<>|*?\r\n]', "_", file_path.name)
                output_files.append({
                    "filename": safe_name,
                    "content": file_path.read_bytes(),
                })
            except Exception as e:
                print(f"Warning: failed to read generated file {file_path}: {e}")
        return output_files
