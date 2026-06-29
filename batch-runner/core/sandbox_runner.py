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

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from core.config import SUBPROCESS_TIMEOUT, SUBPROCESS_MEMORY_GB, DEFAULT_TOKENS
from core.artifact_verifier import verify_artifacts
from core.deliverable_contract import (
    DeliverableContract,
    infer_deliverable_contract,
    select_generated_artifacts,
    validate_contract,
)
from core.dependency_resolver import (
    DependencyManifest,
    load_base_packages,
    probe_imports,
    resolve,
)
from core.file_preview import build_file_structure_info, generate_all_previews
from core.llm_client import complete
from core.output_qa import run_output_qa
from core.prompt_loader import load_prompt, render_prompt
from core.sandbox_cache import build_cache
from core.skills_registry import SkillsRegistry
from core.subprocess_runner import SubprocessRunner, extract_code, extract_description

DEFAULT_SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "gdpval-sandbox:latest")

MANIFEST_SCHEMA_VERSION = "1.0"


def _sha256_text(text: str) -> str:
    import hashlib
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


# Local filesystem roots that must never appear in the manifest or repair prompt.
# Computed once; longest first so nested roots (e.g. the temp dir under $HOME) are
# redacted before the shorter prefix.
_REDACT_ROOTS = sorted(
    {
        r
        for r in (
            os.path.realpath(tempfile.gettempdir()),
            tempfile.gettempdir(),
            "/private/var/folders",
            "/var/folders",
            os.path.expanduser("~"),
        )
        if r and r not in ("/", "")
    },
    key=len,
    reverse=True,
)


def _sanitize_tail(text: Optional[str], limit: int = 600) -> str:
    """Trim to the last ``limit`` chars and redact local absolute paths.

    stdout/stderr tails come from executed code (e.g. a traceback referencing the
    sandbox temp dir). Redacting host roots keeps the manifest and repair prompt
    free of local filesystem layout while preserving the useful error text.
    """
    if not text:
        return ""
    s = text[-limit:]
    for root in _REDACT_ROOTS:
        if root in s:
            repl = "~" if root == os.path.expanduser("~") else "<tmp>"
            s = s.replace(root, repl)
    return s

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
        repair: Optional[dict] = None,
        output_qa: Optional[dict] = None,
        manifest: Optional[dict] = None,
        cache: Optional[dict] = None,
        contract: Optional[dict] = None,
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

        # Output control-loop configuration (conservative defaults).
        self.repair_cfg = {"enabled": True, "max_attempts": 1, **(repair or {})}
        self.output_qa_cfg = {
            "enabled": True,
            "render": True,
            "max_pages_per_artifact": 3,
            "blank_page_threshold": 0.999,
            **(output_qa or {}),
        }
        self.manifest_cfg = {
            "enabled": True,
            "filename": "manifest.json",
            "include_in_files": True,
            **(manifest or {}),
        }
        self.cache_cfg = {"enabled": False, **(cache or {})}
        self.contract_cfg = dict(contract or {})
        self._cache = build_cache(self.cache_cfg)

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
        """Generate code, run it in the sandbox, then verify/QA/repair the output.

        Flow per attempt: augment prompt (contract + skills + deps + reflection)
        → generate code → execute → select generated artifacts → validate against
        the deliverable contract → deterministic verify + render QA. If blocking
        failures remain and the repair budget allows, build a focused reflection
        and regenerate. A ``manifest.json`` capturing every attempt is emitted.
        """
        try:
            ref_files = reference_files or []

            # Perception context (skills) + deterministic deliverable contract.
            skills = self.registry.select(ref_files, task_prompt, max_skills=self.max_skills)
            contract = infer_deliverable_contract(task_prompt, ref_files, self.contract_cfg)

            max_attempts = (
                int(self.repair_cfg.get("max_attempts", 1))
                if self.repair_cfg.get("enabled", True)
                else 0
            )

            attempts: List[dict] = []
            reflection: Optional[str] = None
            best: Optional[dict] = None

            for attempt_idx in range(max_attempts + 1):
                attempt = self._run_attempt(
                    attempt_idx=attempt_idx,
                    task_prompt=task_prompt,
                    model=model,
                    ref_files=ref_files,
                    occupation=occupation,
                    experiment_prompt=experiment_prompt,
                    skills=skills,
                    contract=contract,
                    reflection=reflection,
                )
                attempts.append(attempt["report"])

                if best is None or self._is_better(attempt, best):
                    best = attempt

                # No code at all → terminal (regenerating a refusal rarely helps).
                if attempt["no_code"]:
                    break
                if not attempt["blocking_errors"]:
                    break
                if attempt_idx >= max_attempts:
                    break
                reflection = attempt["reflection_for_next"]

            return self._finalize(best, attempts, skills, contract, ref_files)

        except Exception as e:  # pragma: no cover - defensive
            return {
                "success": False,
                "text": "",
                "files": [],
                "error": f"Sandbox code generation failed: {str(e)}",
            }

    # ── single attempt ────────────────────────────────────────────────────
    def _run_attempt(
        self,
        attempt_idx: int,
        task_prompt: str,
        model: str,
        ref_files: List[str],
        occupation: str,
        experiment_prompt: Optional[dict],
        skills,
        contract: DeliverableContract,
        reflection: Optional[str],
    ) -> dict:
        manifest = resolve(
            reference_files=ref_files,
            task_text=task_prompt,
            base_packages=self._base_packages,
        )
        augmented = self._augment_prompt(
            task_prompt, ref_files, skills, manifest, contract, reflection
        )
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
        response_text = response.choices[0].message.content or ""
        code = extract_code(response_text)

        if not code:
            return {
                "no_code": True,
                "executor": "none",
                "result": {
                    "success": False,
                    "text": "",
                    "deliverable_text": "",
                    "files": [],
                    "error": f"No Python code found in LLM response. "
                             f"Response: {response_text[:200]}...",
                },
                "manifest": manifest,
                "blocking_errors": ["no_code: model produced no runnable Python"],
                "artifacts": [],
                "contract_validation": None,
                "verification": None,
                "output_qa": None,
                "reflection_for_next": None,
                "report": {
                    "attempt": attempt_idx,
                    "status": "failed_execution",
                    "executor": "none",
                    "blocking_errors": ["no_code"],
                    "stdout_tail": "",
                    "stderr_tail": response_text[:300],
                },
            }

        deliverable_text = extract_description(response_text)
        # Re-resolve including the code's imports for a sharper missing-dep signal.
        manifest = resolve(
            reference_files=ref_files,
            task_text=task_prompt,
            code=code,
            base_packages=self._base_packages,
        )

        executor_used, result = self._execute(code, ref_files, manifest)
        result["deliverable_text"] = deliverable_text

        # Inspect the produced artifacts in an isolated workspace.
        analysis = self._analyze_output(
            result, ref_files, contract, task_prompt, executor_used, manifest
        )

        blocking = list(analysis["blocking_errors"])
        if not result.get("success"):
            tail = _sanitize_tail(result.get("error"), limit=600)
            blocking.insert(0, f"execution_failed: {tail}")

        status = self._status_for(attempt_idx, result, analysis, blocking)
        reflection_for_next = self._build_reflection(
            contract, blocking, code, result, analysis
        ) if blocking else None

        return {
            "no_code": False,
            "executor": executor_used,
            "result": result,
            "manifest": manifest,
            "code": code,
            "blocking_errors": blocking,
            "artifacts": analysis["artifact_names"],
            "contract_validation": analysis["contract_validation"],
            "verification": analysis["verification"],
            "output_qa": analysis["output_qa"],
            "import_probe": analysis["import_probe"],
            "reflection_for_next": reflection_for_next,
            "report": {
                "attempt": attempt_idx,
                "status": status,
                "executor": executor_used,
                "code_sha256": _sha256_text(code),
                "blocking_errors": blocking,
                "generated_artifacts": analysis["artifact_names"],
                "stdout_tail": _sanitize_tail(result.get("text"), limit=600),
                "stderr_tail": _sanitize_tail(result.get("error"), limit=600),
            },
        }

    def _analyze_output(
        self,
        result: dict,
        ref_files: List[str],
        contract: DeliverableContract,
        task_prompt: str,
        executor_used: str,
        dep_manifest: Optional[DependencyManifest] = None,
    ) -> dict:
        """Materialize returned files and run contract + verify + render QA."""
        files = result.get("files") or []
        with tempfile.TemporaryDirectory(prefix="gdpval_qa_") as qa_root:
            inspect_dir = Path(qa_root) / "artifacts"
            inspect_dir.mkdir(parents=True, exist_ok=True)
            for f in files:
                try:
                    (inspect_dir / f["filename"]).write_bytes(f.get("content", b""))
                except Exception:
                    continue

            artifacts = select_generated_artifacts(inspect_dir, reference_files=[])
            contract_validation = validate_contract(contract, artifacts)
            verification = verify_artifacts(artifacts, contract, workdir=inspect_dir)
            verification_dict = verification.to_dict()
            # Strip ephemeral QA-workspace absolute paths from the manifest.
            for art in verification_dict.get("artifacts", []):
                art["path"] = art.get("rel_path", art.get("path"))

            render_dir = Path(qa_root) / "render"
            vcfg = self.output_qa_cfg.get("vision", {}) or {}
            output_qa = run_output_qa(
                artifacts,
                contract=contract,
                config=self.output_qa_cfg,
                out_dir=render_dir,
                task_text=task_prompt,
                vision_client=self.llm_client if vcfg.get("enabled") else None,
                cache=self._cache,
            )

            output_qa_dict = output_qa.to_dict()
            for rr in output_qa_dict.get("render_reports", []):
                rr["rendered_images"] = [os.path.basename(p) for p in rr.get("rendered_images", [])]

            # Importability probe of the resolved dependencies (accurate only for
            # local execution; for Docker the host can't see image packages).
            required_pkgs = list(getattr(dep_manifest, "required", []) or [])
            probe = probe_imports(
                required_pkgs,
                enabled=(executor_used == "local"),
                env="host" if executor_used == "local" else "image",
            )

            blocking: List[str] = []
            blocking += contract_validation.blocking_errors
            blocking += verification.blocking_errors
            blocking += output_qa.blocking_errors

            return {
                "artifact_names": [a.name for a in artifacts],
                "contract_validation": contract_validation.to_dict(),
                "verification": verification_dict,
                "output_qa": output_qa_dict,
                "import_probe": probe.to_dict(),
                "blocking_errors": blocking,
                "warnings": (
                    contract_validation.warnings
                    + verification.warnings
                    + output_qa.warnings
                ),
            }

    @staticmethod
    def _is_better(candidate: dict, current: dict) -> bool:
        """Prefer clean > more artifacts > fewer blocking > executed."""
        def score(a: dict):
            ok = 1 if not a["blocking_errors"] else 0
            ran = 1 if a["result"].get("success") else 0
            nfiles = len(a["result"].get("files") or [])
            return (ok, ran, nfiles, -len(a["blocking_errors"]))
        return score(candidate) > score(current)

    @staticmethod
    def _status_for(attempt_idx: int, result: dict, analysis: dict, blocking: List[str]) -> str:
        if not blocking:
            return "ok" if attempt_idx == 0 else "repaired_ok"
        if not result.get("success"):
            return "failed_execution"
        if analysis["contract_validation"] and analysis["contract_validation"]["blocking_errors"]:
            return "failed_contract"
        return "failed_verification"

    def _finalize(
        self,
        best: dict,
        attempts: List[dict],
        skills,
        contract: DeliverableContract,
        ref_files: List[str],
    ) -> dict:
        result = dict(best["result"])
        executor_used = best["executor"]
        manifest = best["manifest"]

        if not best["blocking_errors"]:
            final_status = "ok" if best["report"]["attempt"] == 0 else "repaired_ok"
        else:
            final_status = best["report"]["status"]

        metadata = self._metadata(executor_used, skills, manifest)
        metadata.update({
            "final_status": final_status,
            "repaired": final_status == "repaired_ok",
            "attempts": [a for a in attempts],
            "deliverable_contract": contract.to_dict(),
            "contract_validation": best.get("contract_validation"),
            "verification": best.get("verification"),
            "output_qa": best.get("output_qa"),
            "import_probe": best.get("import_probe"),
            "blocking_errors": best["blocking_errors"],
        })
        result["metadata"] = metadata
        result["final_status"] = final_status
        result["qa_ok"] = not best["blocking_errors"]

        manifest_doc = self._build_manifest(
            executor_used, skills, manifest, contract, attempts, best,
            final_status, ref_files,
        )
        result["sandbox_manifest"] = manifest_doc
        if self.manifest_cfg.get("enabled", True) and self.manifest_cfg.get("include_in_files", True):
            files = list(result.get("files") or [])
            files.append({
                "filename": self.manifest_cfg.get("filename", "manifest.json"),
                "content": json.dumps(manifest_doc, indent=2, default=str).encode("utf-8"),
            })
            result["files"] = files
        return result

    def _build_manifest(
        self, executor_used, skills, manifest, contract, attempts, best,
        final_status, ref_files,
    ) -> dict:
        return {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "execution_mode": "sandbox",
            "sandbox_backend": "docker" if executor_used == "docker" else "local_fallback",
            "selected_skills": [s.name for s in skills],
            "dependency_resolution": manifest.to_dict(),
            "dependency_import_probe": best.get("import_probe"),
            "deliverable_contract": contract.to_dict(),
            "reference_files": [os.path.basename(f) for f in ref_files],
            "generated_artifacts": best.get("artifacts", []),
            "selected_primary_artifacts": (
                best.get("contract_validation", {}) or {}
            ).get("matched_primary", []),
            "verification_report": best.get("verification"),
            "render_report": (best.get("output_qa") or {}).get("render_reports"),
            "vision_qa_report": (best.get("output_qa") or {}).get("vision_qa"),
            "attempts": attempts,
            "final_status": final_status,
        }

    # ── prompt augmentation ──────────────────────────────────────────────
    def _augment_prompt(
        self,
        task_prompt: str,
        reference_files: List[str],
        skills,
        manifest: DependencyManifest,
        contract: Optional[DeliverableContract] = None,
        reflection: Optional[str] = None,
    ) -> str:
        parts: List[str] = []

        # A repair reflection (if any) goes first so the model addresses it.
        if reflection:
            parts.append(reflection)

        file_structure_info = build_file_structure_info(reference_files or [])
        if file_structure_info:
            parts.append(file_structure_info)

        skills_manual = self.registry.render_manual(skills)
        if skills_manual:
            parts.append(skills_manual)

        dep_hint = manifest.to_prompt_hint()
        if dep_hint:
            parts.append(dep_hint)

        if contract is not None:
            parts.append(contract.to_prompt_section())

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

    def _build_reflection(
        self,
        contract: DeliverableContract,
        blocking_errors: List[str],
        code: str,
        result: dict,
        analysis: dict,
    ) -> str:
        """A focused [REFLECTION] block fed back to the model for the next attempt."""
        lines = [
            "[REFLECTION]",
            "Your previous attempt did NOT satisfy the deliverable contract. "
            "Regenerate the COMPLETE solution and fix every issue below.",
            "",
            "Blocking problems to fix:",
        ]
        for err in blocking_errors[:12]:
            lines.append(f"- {err}")

        warnings = analysis.get("warnings") or []
        if warnings:
            lines.append("")
            lines.append("Secondary warnings (address if relevant):")
            for w in warnings[:6]:
                lines.append(f"- {w}")

        lines.append("")
        lines.append(contract.to_prompt_section())

        stdout_tail = _sanitize_tail(result.get("text"), limit=800)
        stderr_tail = _sanitize_tail(result.get("error"), limit=800)
        if stdout_tail.strip():
            lines += ["", "Previous stdout (tail):", stdout_tail]
        if stderr_tail.strip():
            lines += ["", "Previous stderr/error (tail):", stderr_tail]

        # Include the prior code when short enough to be useful context.
        if code and len(code) <= 4000:
            lines += ["", "Your previous code (fix and resend in full):",
                      "----", code, "----"]
        lines.append("[/REFLECTION]")
        return "\n".join(lines)

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
