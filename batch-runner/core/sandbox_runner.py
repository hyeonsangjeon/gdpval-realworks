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
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

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
from core.execution_errors import classify_execution_error
from core.execution_metrics import (
    add_durations_ms,
    bounded_count,
    bounded_duration_ms,
)

from core.llm_client import complete
from core.output_qa import run_output_qa
from core.prompt_loader import load_prompt, render_prompt
from core.reference_integrity import (
    copy_verified_reference,
    stage_verified_references,
)
from core.prompt_sections import (
    DEFAULT_SECTIONS,
    SectionContext,
    assemble_sections,
)
from core.sandbox_cache import build_cache
from core.skills_registry import SkillsRegistry
from core.subprocess_runner import (
    RUNNER_FILENAME,
    SubprocessRunner,
    build_execution_launcher,
    extract_code,
    extract_description,
    parse_execution_streams,
)

DEFAULT_SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "gdpval-sandbox:latest")

MANIFEST_SCHEMA_VERSION = "1.0"

# Minimum code_generation budget considered safe when reasoning_effort is "high".
# gpt-5.4 at high reasoning can spend >32k tokens on hidden reasoning on complex
# GDPVal sandbox prompts, leaving no room for visible code ("No Python code
# found") — and can also exceed the 480s LLM-client timeout. Below this budget
# with high effort we warn loudly. See tasks/0701_wednesday/sandbox_ab_smoke_pr57.md.
SAFE_HIGH_CODE_BUDGET = 32768


def _sha256_text(text: str) -> str:
    import hashlib
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _response_usage(response) -> Optional[dict]:
    """Return a compact, provider-tolerant token usage record."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None

    def _get(obj, key):
        return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)

    result = {
        "prompt_tokens": _get(usage, "prompt_tokens"),
        "completion_tokens": _get(usage, "completion_tokens"),
        "total_tokens": _get(usage, "total_tokens"),
    }
    details = _get(usage, "completion_tokens_details")
    reasoning_tokens = _get(details, "reasoning_tokens") if details is not None else None
    if reasoning_tokens is not None:
        result["reasoning_tokens"] = reasoning_tokens
    return result


def _numeric_metric(value) -> Optional[float]:
    """Return a bounded timing value, otherwise ``None``."""
    return bounded_duration_ms(value)


def _github_run_context() -> dict:
    """Capture non-secret CI identifiers for relay/attempt correlation."""
    keys = {
        "run_id": "GITHUB_RUN_ID",
        "run_number": "GITHUB_RUN_NUMBER",
        "run_attempt": "GITHUB_RUN_ATTEMPT",
        "workflow": "GITHUB_WORKFLOW",
        "sha": "GITHUB_SHA",
    }
    return {name: os.environ[env] for name, env in keys.items() if os.getenv(env)}


def _text_fingerprint(text: Optional[str]) -> dict:
    """Describe text without persisting its potentially sensitive contents."""
    value = text or ""
    return {
        "chars": len(value),
        "sha256": _sha256_text(value) if value else None,
    }


def _blocking_error_categories(errors: List[str]) -> List[str]:
    """Reduce blocking details to stable, non-sensitive category labels."""
    categories: List[str] = []
    for error in errors:
        lowered = (error or "").lower()
        if lowered.startswith("syntax_preflight_failed:"):
            category = "syntax_error"
        elif lowered.startswith("execution_failed["):
            category = lowered.split("[", 1)[1].split("]", 1)[0]
        elif lowered.startswith("execution_failed:"):
            category = classify_execution_error(error) or "execution_error"
        elif "no runnable python" in lowered or lowered == "no_code":
            category = "no_code"
        elif "deliverable" in lowered or "primary" in lowered or "contract" in lowered:
            category = "deliverable_contract"
        elif "blank" in lowered or "render" in lowered or "verification" in lowered:
            category = "output_verification"
        else:
            category = "output_validation"
        if category not in categories:
            categories.append(category)
    return categories


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


# What the repair loop carries back to the model when it asks for the code a
# second time: how much of the failed run's own output, and how many lines of
# each kind go with it. Named here rather than typed at each call site because
# core/execution_envelope_preflight.py has to price the repair prompt, and a
# figure typed over there would go stale the moment one of these changed.
REFLECTION_STDOUT_TAIL_CHARS = 800
REFLECTION_STDERR_TAIL_CHARS = 800
EXECUTION_ERROR_TAIL_CHARS = 600
REFLECTION_MAX_BLOCKING_ERRORS = 12
REFLECTION_MAX_WARNINGS = 6
REFLECTION_PRIOR_CODE_MAX_CHARS = 4000


def _sanitize_tail(
    text: Optional[str], limit: int = EXECUTION_ERROR_TAIL_CHARS
) -> str:
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


def execution_failure_blocking_error(
    category: Optional[str], error_text: Optional[str]
) -> str:
    """The blocking line a run that stopped on an error contributes.

    Named rather than formatted where it is used because
    :func:`widest_repair_prompt_characters` has to build one at its full width
    in order to price the repair prompt, and a second copy of this wording is
    exactly how two figures start disagreeing about the same line.
    """
    return (
        f"execution_failed[{category or 'execution_error'}]: "
        f"{_sanitize_tail(error_text, limit=EXECUTION_ERROR_TAIL_CHARS)}"
    )


# Built-in fallback for the self-repair reflection wording. The canonical copy
# lives in the prompt spec (`reflection_strings:` in the codegen YAML) so it can
# be edited in one place; these defaults keep _build_reflection working when a
# spec omits the block. Keep them in sync with prompts/sandbox_occupation_codegen.yaml.
_DEFAULT_REFLECTION_STRINGS = {
    "open": "[REFLECTION]",
    "intro": (
        "Your previous attempt did NOT satisfy the deliverable contract. "
        "Regenerate the COMPLETE solution and fix every issue below."
    ),
    "blocking_header": "Blocking problems to fix:",
    "strategy_header": "Required repair strategy:",
    "warnings_header": "Secondary warnings (address if relevant):",
    "stdout_header": "Previous stdout (tail):",
    "stderr_header": "Previous stderr/error (tail):",
    "code_header": "Your previous code (fix and resend in full):",
    "code_fence": "----",
    "close": "[/REFLECTION]",
}


def reflection_strings(prompt_data: Mapping[str, Any]) -> Dict[str, str]:
    """The repair prompt's wording: the spec's where it has one, else the default."""
    written = prompt_data.get("reflection_strings") or {}
    merged = {**_DEFAULT_REFLECTION_STRINGS, **written}
    return {str(key): str(value) for key, value in merged.items()}


def reflection_repair_guidance(
    prompt_data: Mapping[str, Any], categories: Sequence[str]
) -> List[str]:
    """The guidance lines the spec holds for these error categories, in order."""
    written = prompt_data.get("repair_guidance") or {}
    return [str(written[c]) for c in categories if written.get(c)]


def render_reflection(
    *,
    strings: Mapping[str, str],
    contract_section: str,
    blocking_errors: Sequence[str],
    guidance: Sequence[str],
    warnings: Sequence[str],
    stdout_tail: str,
    stderr_tail: str,
    code: str,
) -> str:
    """Lay out one repair prompt, and apply the limits on how much it may carry.

    The only place the [REFLECTION] block is built. ``SandboxRunner`` calls this
    on a failed attempt; ``widest_repair_prompt_characters`` calls it to measure
    what such a block comes to. Two renderers would be two answers, and the one
    used for pricing would be the one nobody noticed drifting.
    """
    lines = [
        strings["open"],
        strings["intro"],
        "",
        strings["blocking_header"],
    ]
    for err in blocking_errors[:REFLECTION_MAX_BLOCKING_ERRORS]:
        lines.append(f"- {err}")

    if guidance:
        lines += ["", strings["strategy_header"]]
        lines.extend(f"- {item}" for item in guidance)

    if warnings:
        lines.append("")
        lines.append(strings["warnings_header"])
        for w in warnings[:REFLECTION_MAX_WARNINGS]:
            lines.append(f"- {w}")

    lines.append("")
    lines.append(contract_section)

    if stdout_tail.strip():
        lines += ["", strings["stdout_header"], stdout_tail]
    if stderr_tail.strip():
        lines += ["", strings["stderr_header"], stderr_tail]

    # Include the prior code when short enough to be useful context.
    if code and len(code) <= REFLECTION_PRIOR_CODE_MAX_CHARS:
        lines += ["", strings["code_header"],
                  strings["code_fence"], code, strings["code_fence"]]
    lines.append(strings["close"])
    return "\n".join(lines)


def narrowest_contract_section() -> str:
    """The least a deliverable contract section can come to, built by the contract.

    ``render_reflection`` appends one of these on every repair prompt, whatever
    the task, so its length is part of what a later turn always carries. The
    figure is taken by building the section rather than by counting its words
    here, so wording edited in :mod:`core.deliverable_contract` moves it.

    Both branches of ``to_prompt_section`` are built and the shorter kept, and
    every field is set to the least that still renders: no notes, no keywords,
    and the shortest count and confidence either can be. A real contract is
    longer, which is the direction that is safe to be wrong in.
    """
    return min(
        (
            DeliverableContract(
                expected_extensions=list(expected),
                min_count=0,
                required_keywords=[],
                notes=[],
                confidence="",  # type: ignore[arg-type]
            ).to_prompt_section()
            for expected in ((), ("",))
        ),
        key=len,
    )


#: Stands in for the model's own earlier code while the words placed around it
#: are measured. One character, taken off again afterwards, so the count covers
#: the runner's own wording without covering the answer it wraps.
_PRIOR_CODE_STAND_IN = "c"

#: What the widest repair prompt is made of, in the order the parts are added.
#: Each name is the English a refusal quotes back, so it reads as a sentence,
#: and each covers its own heading as well as its contents — a part is measured
#: by what it adds to the prompt, and a heading only appears when it does.
_REPAIR_PROMPT_PARTS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("the opening, the instruction and the close it always carries", ()),
    (
        "up to twelve blocking-error lines under their heading, the first of "
        "them the failure that stopped the run",
        ("blocking_errors",),
    ),
    (
        "the repair guidance the committed prompt holds, under its heading",
        ("guidance",),
    ),
    ("up to six secondary warnings under their heading", ("warnings",)),
    ("the deliverable contract section, at its narrowest", ("contract_section",)),
    ("the last of what the code printed, under its heading", ("stdout_tail",)),
    (
        "the last of what it printed as an error, under its heading",
        ("stderr_tail",),
    ),
)


def widest_repair_prompt_characters(
    prompt_name: Optional[str] = None,
) -> Dict[str, int]:
    """What one repair prompt comes to, part by part, worked out by building it.

    Every figure returned is the length of a string this module really renders,
    through the same :func:`render_reflection` a repair turn uses. Nothing is
    added up from widths written down a second time, so a header edited in
    ``prompts/<name>.yaml``, a limit changed above, or a repair-guidance entry
    added all move this with them.

    The parts are added one at a time and each figure is what that part added,
    so they come to the whole prompt exactly. They are kept apart rather than
    summed here so a refusal can say what the total is made of.

    The model's own earlier code is the one thing left out. The words placed
    around it are counted; the code between them is not, because it is the
    model's earlier answer and a cost sum that charges ``max_output_tokens`` for
    every earlier answer has already paid for those words once.

    Raises whatever :func:`core.prompt_loader.load_prompt` raises when the named
    prompt cannot be read. There is no reading of an unreadable prompt that
    would let this return a smaller answer instead.
    """
    prompt_data = load_prompt(prompt_name or SandboxRunner.DEFAULT_PROMPT)
    strings = reflection_strings(prompt_data)
    every_category = list((prompt_data.get("repair_guidance") or {}).keys())

    widest = {
        "contract_section": narrowest_contract_section(),
        "blocking_errors": (
            [execution_failure_blocking_error(None, "x" * EXECUTION_ERROR_TAIL_CHARS)]
            + [""] * (REFLECTION_MAX_BLOCKING_ERRORS - 1)
        ),
        "guidance": reflection_repair_guidance(prompt_data, every_category),
        "warnings": [""] * REFLECTION_MAX_WARNINGS,
        "stdout_tail": "o" * REFLECTION_STDOUT_TAIL_CHARS,
        "stderr_tail": "e" * REFLECTION_STDERR_TAIL_CHARS,
        "code": "",
    }
    so_far: Dict[str, Any] = {
        "contract_section": "",
        "blocking_errors": [],
        "guidance": [],
        "warnings": [],
        "stdout_tail": "",
        "stderr_tail": "",
        "code": "",
    }

    measured: Dict[str, int] = {}
    counted = 0
    for what, fields in _REPAIR_PROMPT_PARTS:
        for field in fields:
            so_far[field] = widest[field]
        now = len(render_reflection(strings=strings, **so_far))
        measured[what] = now - counted
        counted = now

    with_the_code = len(
        render_reflection(
            strings=strings, **{**so_far, "code": _PRIOR_CODE_STAND_IN}
        )
    )
    measured["the words placed around the model's earlier code"] = (
        with_the_code - counted - len(_PRIOR_CODE_STAND_IN)
    )
    return measured

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
    """Return True if the sandbox image is present locally.

    ``docker image inspect <name:tag>`` is the natural check, but under Docker
    Desktop's containerd image store (the current default) tag→image resolution
    for that endpoint intermittently fails with "No such image" even when the
    tag is present and runnable — most reproducibly right after a daemon
    restart. ``docker image ls -q <ref>`` resolves the same tag reliably in that
    store, so we fall back to it before concluding the image is missing. Without
    this, a present, working sandbox image is misdetected as absent and the
    runner silently degrades to hardened local execution.
    """
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            return True
    except Exception:
        pass
    # Fallback: reliable under the containerd snapshotter image store.
    try:
        proc = subprocess.run(
            ["docker", "image", "ls", "--quiet", image],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0 and bool(proc.stdout.strip())
    except Exception:
        return False


class SandboxRunner:
    """LLM code generation → skill-aware, containerized execution."""

    #: Whether this run place opens a new request for each turn the model
    #: takes. ``True`` here: the repair loop in ``run`` is an ordinary Python
    #: ``for`` loop, and every go through it calls ``complete`` again with the
    #: whole ``max_completion_tokens`` budget. Nothing joins those calls into
    #: one reply, so no single cap covers the attempt.
    #:
    #: Read by core/execution_envelope_preflight.py — see the note on
    #: ``CodeInterpreterRunner.SENDS_A_FRESH_REQUEST_PER_TURN``. It costs
    #: nothing while the repair loop is switched off and there is only one
    #: turn to bill; it starts to matter the moment that block changes.
    SENDS_A_FRESH_REQUEST_PER_TURN = True

    #: Which prompt sections this run place fills from the reference files.
    #: All three, though this one reaches them by name rather than inline: the
    #: prompt spec's ``sections:`` list — ``DEFAULT_SECTIONS`` when the spec is
    #: silent — is handed to ``assemble_sections``, and
    #: core/prompt_sections.py's ``SECTION_PROVIDERS`` maps ``file_structure``
    #: and ``previews`` onto the same two functions the host runner calls, plus
    #: ``available_files``. A spec may switch any of them off, so this tuple is
    #: what the run place *can* send, which is what a ceiling has to be built
    #: on.
    #:
    #: Read by core/execution_envelope_preflight.py — see the note on
    #: ``CodeInterpreterRunner.REFERENCE_FILE_PROMPT_SECTIONS``.
    REFERENCE_FILE_PROMPT_SECTIONS = (
        "file_structure",
        "previews",
        "available_files",
    )

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
        metrics: Optional[dict] = None,
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

        # Guard: a high-reasoning + small-budget sandbox codegen config is a known
        # empty-output / timeout trap. Warn once at construction so a large run is
        # never silently misconfigured (warning only — behavior is unchanged, and
        # this is scoped to sandbox mode). See SAFE_HIGH_CODE_BUDGET above.
        if (self.reasoning_effort or "").lower() == "high" \
                and self.max_completion_tokens < SAFE_HIGH_CODE_BUDGET:
            print(
                f"⚠️  [sandbox] reasoning_effort='high' with code_generation="
                f"{self.max_completion_tokens} risks EMPTY output (reasoning can "
                f"consume the whole budget) and may exceed the 480s client timeout. "
                f"Recommend reasoning_effort<=medium and/or code_generation>="
                f"{SAFE_HIGH_CODE_BUDGET}."
            )

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
        self.metrics_enabled = (
            isinstance(metrics, dict) and metrics.get("enabled") is True
        )
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
        perception_text: Optional[str] = None,
    ) -> dict:
        """Generate code, run it in the sandbox, then verify/QA/repair the output.

        Flow per attempt: augment prompt (contract + skills + deps + reflection)
        → generate code → execute → select generated artifacts → validate against
        the deliverable contract → deterministic verify + render QA. If blocking
        failures remain and the repair budget allows, build a focused reflection
        and regenerate. A ``manifest.json`` capturing every attempt is emitted.

        ``perception_text`` is the optional host audio/video analysis block. The
        sandbox owns its *placement* (the ``perception_analysis`` spec section),
        so step2 passes it through here instead of prepending it to the task.
        """
        run_started = time.perf_counter()
        reference_stage = self._stage_reference_files(reference_files or [])
        reference_stage_entered = False
        try:
            ref_files = reference_stage.__enter__()
            reference_stage_entered = True

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
                    perception_text=perception_text,
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

            finalized = self._finalize(best, attempts, skills, contract, ref_files)
            if self.metrics_enabled:
                task_wall_time_ms = bounded_duration_ms(
                    (time.perf_counter() - run_started) * 1000,
                )
                if task_wall_time_ms is not None:
                    finalized["execution_metrics"]["task_wall_time_ms"] = task_wall_time_ms
            return finalized

        except Exception as e:  # pragma: no cover - defensive
            return {
                "success": False,
                "text": "",
                "files": [],
                "error": f"Sandbox code generation failed: {str(e)}",
            }
        finally:
            if reference_stage_entered:
                reference_stage.__exit__(None, None, None)

    def _stage_reference_files(self, reference_files: List[str]):
        return stage_verified_references(reference_files)

    def _host_reference_access(self) -> bool:
        return True

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
        perception_text: Optional[str] = None,
    ) -> dict:
        dependency_time_ms = 0.0
        dependency_started = time.perf_counter()
        manifest = resolve(
            reference_files=ref_files,
            task_text=task_prompt,
            base_packages=self._base_packages,
        )
        dependency_time_ms += (time.perf_counter() - dependency_started) * 1000
        augmented = self._augment_prompt(
            task_prompt, ref_files, skills, manifest, contract, reflection,
            perception_text=perception_text,
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
        prompt_sha256 = _sha256_text(
            rendered["system_message"] + "\n\n" + rendered["user_prompt"]
        )
        response, llm_latency_ms = complete(
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
                    "prompt_sha256": prompt_sha256,
                    "llm_latency_ms": _numeric_metric(llm_latency_ms),
                    "usage": _response_usage(response),
                    **self._attempt_metrics(
                        llm_latency_ms=llm_latency_ms,
                        dependency_time_ms=dependency_time_ms,
                    ),
                    "blocking_error_count": 1,
                    "blocking_error_categories": ["no_code"],
                    "response": _text_fingerprint(response_text),
                    "error_category": "no_code",
                },
            }

        deliverable_text = extract_description(response_text)
        # Re-resolve including the code's imports for a sharper missing-dep signal.
        dependency_started = time.perf_counter()
        manifest = resolve(
            reference_files=ref_files,
            task_text=task_prompt,
            code=code,
            base_packages=self._base_packages,
        )
        dependency_time_ms += (time.perf_counter() - dependency_started) * 1000

        tool_started = time.perf_counter()
        executor_used, result = self._execute(code, ref_files, manifest)
        tool_time_ms = (time.perf_counter() - tool_started) * 1000
        result["deliverable_text"] = deliverable_text

        preflight = result.get("preflight")
        if isinstance(preflight, dict) and preflight.get("ok") is False:
            location = f"line {preflight.get('line')}"
            if preflight.get("offset") is not None:
                location += f", column {preflight['offset']}"
            blocking = [
                "syntax_preflight_failed: "
                f"{preflight.get('error_type', 'SyntaxError')} at {location}"
            ]
            analysis = {"warnings": []}
            return {
                "no_code": False,
                "executor": executor_used,
                "result": result,
                "manifest": manifest,
                "code": code,
                "blocking_errors": blocking,
                "artifacts": [],
                "contract_validation": None,
                "verification": None,
                "output_qa": None,
                "import_probe": None,
                "reflection_for_next": self._build_reflection(
                    contract, blocking, code, result, analysis
                ),
                "report": {
                    "attempt": attempt_idx,
                    "status": "failed_execution",
                    "executor": executor_used,
                    "prompt_sha256": prompt_sha256,
                    "code_sha256": _sha256_text(code),
                    "llm_latency_ms": _numeric_metric(llm_latency_ms),
                    "usage": _response_usage(response),
                    **self._attempt_metrics(
                        llm_latency_ms=llm_latency_ms,
                        tool_time_ms=tool_time_ms,
                        dependency_time_ms=dependency_time_ms,
                        tool_call_count=1,
                    ),
                    "blocking_error_count": 1,
                    "blocking_error_categories": ["syntax_error"],
                    "generated_artifacts": [],
                    "preflight": preflight,
                    "error_category": "syntax_error",
                },
            }

        # Inspect the produced artifacts in an isolated workspace.
        verification_started = time.perf_counter()
        analysis = self._analyze_output(
            result, ref_files, contract, task_prompt, executor_used, manifest
        )
        verification_time_ms = (time.perf_counter() - verification_started) * 1000

        blocking = list(analysis["blocking_errors"])
        execution_error_category = (
            result.get("error_category")
            or classify_execution_error(result.get("error"))
        )
        if not result.get("success"):
            blocking.insert(
                0,
                execution_failure_blocking_error(
                    execution_error_category, result.get("error")
                ),
            )

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
                "prompt_sha256": prompt_sha256,
                "code_sha256": _sha256_text(code),
                "llm_latency_ms": _numeric_metric(llm_latency_ms),
                "usage": _response_usage(response),
                **self._attempt_metrics(
                    llm_latency_ms=llm_latency_ms,
                    tool_time_ms=tool_time_ms,
                    verification_time_ms=verification_time_ms,
                    dependency_time_ms=dependency_time_ms,
                    tool_call_count=1,
                ),
                "blocking_error_count": len(blocking),
                "blocking_error_categories": _blocking_error_categories(blocking),
                "generated_artifacts": analysis["artifact_names"],
                "preflight": preflight,
                "stdout": _text_fingerprint(result.get("text")),
                "stderr": _text_fingerprint(result.get("error")),
                "error_category": execution_error_category,
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
        """Prefer clean, then actually executed attempts, then useful output."""
        def score(a: dict):
            ok = 1 if not a["blocking_errors"] else 0
            preflight = a.get("result", {}).get("preflight") or {}
            execution_attempted = 1 if (
                a.get("executor") in {"local", "docker"}
                and preflight.get("ok") is True
            ) else 0
            succeeded = 1 if a["result"].get("success") else 0
            nfiles = len(a["result"].get("files") or [])
            return (
                ok,
                execution_attempted,
                succeeded,
                nfiles,
                -len(a["blocking_errors"]),
            )
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
        if self.metrics_enabled:
            validated_artifact_count = (
                len(best.get("artifacts") or [])
                if final_status in {"ok", "repaired_ok"}
                else 0
            )
            result["execution_metrics"] = self._aggregate_execution_metrics(
                attempts,
                validated_artifact_count=validated_artifact_count,
            )

        manifest_doc = self._build_manifest(
            executor_used, skills, manifest, contract, attempts, best,
            final_status, ref_files,
        )
        result["sandbox_manifest"] = manifest_doc
        if self.manifest_cfg.get("enabled", True) and self.manifest_cfg.get("include_in_files", True):
            files = list(result.get("files") or [])
            files.append({
                "filename": self.manifest_cfg.get("filename", "manifest.json"),
                "content": json.dumps(
                    manifest_doc,
                    indent=2,
                    default=str,
                    allow_nan=False,
                ).encode("utf-8"),
            })
            result["files"] = files
        return result

    @staticmethod
    def _aggregate_execution_metrics(
        attempts: List[dict],
        validated_artifact_count: int = 0,
    ) -> dict:
        """Aggregate bounded phase timings for a newly executed sandbox task."""
        totals = {
            "model_time_ms": 0.0,
            "tool_time_ms": 0.0,
            "verification_time_ms": 0.0,
            "dependency_time_ms": 0.0,
        }
        for attempt in attempts:
            phase_times = attempt.get("phase_times_ms") or {}
            for output_key, phase_key in (
                ("model_time_ms", "model"),
                ("tool_time_ms", "tool"),
                ("verification_time_ms", "verification"),
                ("dependency_time_ms", "dependency"),
            ):
                value = _numeric_metric(phase_times.get(phase_key))
                if value is not None:
                    combined = add_durations_ms(totals[output_key], value)
                    totals[output_key] = combined if combined is not None else totals[output_key]

        attempt_count = bounded_count(len(attempts)) or 0
        tool_call_count = bounded_count(sum(
            int(attempt.get("tool_call_count") or 0) for attempt in attempts
        )) or 0

        return {
            "schema_version": "1.0",
            "task_wall_time_ms": 0.0,
            **{key: round(value, 2) for key, value in totals.items()},
            "attempt_count": attempt_count,
            "tool_call_count": tool_call_count,
            "validated_artifact_count": bounded_count(validated_artifact_count) or 0,
        }

    def _attempt_metrics(
        self,
        llm_latency_ms=None,
        tool_time_ms: float = 0.0,
        verification_time_ms: float = 0.0,
        dependency_time_ms: float = 0.0,
        tool_call_count: int = 0,
    ) -> dict:
        if not self.metrics_enabled:
            return {}
        return {
            "phase_times_ms": {
                "model": _numeric_metric(llm_latency_ms),
                "tool": round(tool_time_ms, 2),
                "verification": round(verification_time_ms, 2),
                "dependency": round(dependency_time_ms, 2),
            },
            "tool_call_count": tool_call_count,
        }

    def _build_manifest(
        self, executor_used, skills, manifest, contract, attempts, best,
        final_status, ref_files,
    ) -> dict:
        preflight = best.get("result", {}).get("preflight") or {}
        backend = {
            "docker": "docker",
            "local": "local_fallback",
            "preflight": "not_executed",
            "none": "not_executed",
        }.get(executor_used, "not_executed")
        if preflight.get("ok") is not True:
            backend = "not_executed"
        return {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "execution_mode": "sandbox",
            "sandbox_backend": backend,
            "sandbox_image": self.image if executor_used == "docker" else None,
            "run_context": _github_run_context(),
            "selected_skills": [s.name for s in skills],
            "selected_skills_detail": [s.to_dict() for s in skills],
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
            "best_attempt": best.get("report", {}).get("attempt"),
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
        perception_text: Optional[str] = None,
    ) -> str:
        """Assemble the sandbox prompt from spec-ordered sections.

        Structure (section order + presence) is owned by the prompt spec's
        ``sections:`` list, falling back to ``DEFAULT_SECTIONS`` (today's order).
        Each section's text comes from a thin provider in ``core.prompt_sections``;
        this method only builds the context and delegates the assembly.
        ``perception_text`` (host audio/video analysis) fills the optional
        ``perception_analysis`` section when the spec enables it.
        """
        ctx = SectionContext(
            task_prompt=task_prompt,
            ref_files=reference_files or [],
            skills=skills,
            manifest=manifest,
            contract=contract,
            reflection=reflection,
            registry=self.registry,
            perception_text=perception_text,
            host_reference_access=self._host_reference_access(),
        )
        section_order = self.prompt_data.get("sections") or DEFAULT_SECTIONS
        return assemble_sections(section_order, ctx)

    def _build_reflection(
        self,
        contract: DeliverableContract,
        blocking_errors: List[str],
        code: str,
        result: dict,
        analysis: dict,
    ) -> str:
        """A focused [REFLECTION] block fed back to the model for the next attempt.

        The wording is authored in the prompt spec (``reflection_strings:`` in the
        codegen YAML) so a researcher can edit it in one place; the layout and the
        safety limits belong to :func:`render_reflection`, which this method feeds
        and which ``core/execution_envelope_preflight.py`` prices. Missing keys
        fall back to ``_DEFAULT_REFLECTION_STRINGS``.
        """
        return render_reflection(
            strings=reflection_strings(self.prompt_data),
            contract_section=contract.to_prompt_section(),
            blocking_errors=blocking_errors,
            guidance=reflection_repair_guidance(
                self.prompt_data, _blocking_error_categories(blocking_errors)
            ),
            warnings=analysis.get("warnings") or [],
            stdout_tail=_sanitize_tail(
                result.get("text"), limit=REFLECTION_STDOUT_TAIL_CHARS
            ),
            stderr_tail=_sanitize_tail(
                result.get("error"), limit=REFLECTION_STDERR_TAIL_CHARS
            ),
            code=code or "",
        )

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
                    "preflight": None,
                    "error_category": "backend_unavailable",
                    "error": f"Sandbox image '{self.image}' not found. Build it: "
                             f"bash sandbox/build.sh",
                }
            print(f"      ⚠️  Sandbox image '{self.image}' missing — falling back to local execution")
        elif self.use_docker == "always":
            return "docker", {
                "success": False,
                "text": "",
                "files": [],
                "preflight": None,
                "error_category": "backend_unavailable",
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
                    copied = copy_verified_reference(src_path, tmpdir)
                    copied_files.append(Path(str(copied)).name)

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

                (Path(tmpdir) / "solution.py").write_text(code, encoding="utf-8")
                (Path(tmpdir) / RUNNER_FILENAME).write_text(
                    build_execution_launcher(copied_files),
                    encoding="utf-8",
                )

                cmd = self._docker_command(tmpdir, skills_mounted)
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=False,
                    timeout=self.timeout + 30,  # allow container start overhead
                )
                stdout_text, stderr_text, preflight, decode_error = parse_execution_streams(
                    result.stdout,
                    result.stderr,
                )

                if result.returncode in (137, -9):
                    return {
                        "success": False,
                        "text": stdout_text,
                        "files": [],
                        "preflight": preflight,
                        "error_category": "out_of_memory",
                        "error": f"memory_error: container killed "
                                 f"(exit {result.returncode}, limit {self.memory_gb}GB)",
                    }
                if result.returncode != 0:
                    category = (
                        "binary_decode_error"
                        if decode_error
                        else (
                            classify_execution_error(stderr_text) or "execution_error"
                        )
                    )
                    return {
                        "success": False,
                        "text": stdout_text,
                        "files": [],
                        "preflight": preflight,
                        "error_category": category,
                        "error": f"Sandbox execution failed (exit {result.returncode}):\n{stderr_text[-1500:]}",
                    }

                if decode_error:
                    return {
                        "success": False,
                        "text": stdout_text,
                        "files": [],
                        "preflight": preflight,
                        "error_category": "binary_decode_error",
                        "error": "Sandbox execution output was not valid UTF-8 text",
                    }

                return {
                    "success": True,
                    "text": stdout_text,
                    "files": self._collect_output_files(tmpdir, copied_files),
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
                    "error": f"Sandbox execution timeout ({self.timeout}s exceeded)",
                }
            except UnicodeDecodeError:
                return {
                    "success": False,
                    "text": "",
                    "files": [],
                    "preflight": None,
                    "error_category": "binary_decode_error",
                    "error": "Sandbox execution output was not valid UTF-8 text",
                }
            except Exception as e:
                return {
                    "success": False,
                    "text": "",
                    "files": [],
                    "preflight": None,
                    "error_category": classify_execution_error(str(e)),
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
        ]
        getuid = getattr(os, "getuid", None)
        getgid = getattr(os, "getgid", None)
        if callable(getuid) and callable(getgid):
            cmd += ["--user", f"{getuid()}:{getgid()}"]
        cmd += [
            "-v", f"{workdir}:/work:rw",
            "-w", "/work",
            "-e", "HOME=/work",
            "-e", "LANG=C.UTF-8",
            "-e", f"PYTHONPATH={pythonpath}",
            # Keep bytecode artifacts out of the bind-mounted workdir.
            "-e", "PYTHONDONTWRITEBYTECODE=1",
        ]
        if self.cpus:
            cmd += ["--cpus", str(self.cpus)]
        cmd += [self.image, "python", "-u", RUNNER_FILENAME]
        return cmd

    @staticmethod
    def _collect_output_files(workdir: str, copied_files: List[str]) -> list:
        """Collect generated files (exclude script, inputs, skills, bytecode)."""
        output_files = []
        skip_names = {
            "solution.py",
            RUNNER_FILENAME,
        } | set(copied_files)
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
