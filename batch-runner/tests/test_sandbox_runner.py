"""Tests for core/sandbox_runner.py

These tests never require Docker or the heavy multimodal deps: the end-to-end
path is exercised through the hardened local fallback (use_docker="never") with
the LLM call patched out.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

import core.sandbox_runner as sr
from core.sandbox_runner import (
    SandboxRunner,
    docker_available,
    docker_image_exists,
)


# ── helpers ──────────────────────────────────────────────────────────────

def _fake_response(content: str):
    """Build a minimal object shaped like an OpenAI chat completion."""
    msg = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


def _patch_complete(content: str):
    """Patch core.sandbox_runner.complete to return our canned response."""
    return patch.object(sr, "complete", lambda **kwargs: (_fake_response(content), {}))


# ── module-level probes ──────────────────────────────────────────────────

def test_docker_available_returns_bool():
    assert isinstance(docker_available(refresh=True), bool)


def test_docker_image_exists_handles_missing_daemon():
    # Whatever the environment, this must return a bool and never raise.
    assert isinstance(docker_image_exists("definitely-not-a-real-image:xyz"), bool)


# ── construction ─────────────────────────────────────────────────────────

def test_init_wires_registry_and_base_packages():
    runner = SandboxRunner(llm_client=object(), use_docker="never")
    assert runner.registry is not None
    assert runner.skills_dir.endswith("skills")
    assert "librosa" in runner._base_packages
    assert runner.image  # default image name


def test_default_prompt_name():
    assert SandboxRunner.DEFAULT_PROMPT == "sandbox_occupation_codegen"


# ── prompt augmentation ──────────────────────────────────────────────────

def test_augment_prompt_includes_skill_and_dep_hints():
    runner = SandboxRunner(llm_client=object(), use_docker="never")
    skills = runner.registry.select(["/data/clip.mp4"], "extract keyframes")
    from core.dependency_resolver import resolve
    manifest = resolve(reference_files=["/data/clip.mp4"], task_text="extract keyframes")
    augmented = runner._augment_prompt("Summarize the video", [], skills, manifest)
    assert "Summarize the video" in augmented
    assert "AVAILABLE SKILLS" in augmented
    assert "opencv-python" in augmented  # dependency hint


# ── execution dispatch ───────────────────────────────────────────────────

def test_execute_never_uses_local_fallback():
    runner = SandboxRunner(llm_client=object(), use_docker="never")
    with patch.object(runner._local, "run_code", return_value={"success": True, "files": []}) as m:
        used, result = runner._execute("print('x')", [], manifest=_dummy_manifest())
    assert used == "local"
    assert result["success"] is True
    m.assert_called_once()


def test_execute_always_without_docker_errors():
    runner = SandboxRunner(llm_client=object(), use_docker="always")
    with patch.object(sr, "docker_available", return_value=False):
        used, result = runner._execute("print('x')", [], manifest=_dummy_manifest())
    assert used == "docker"
    assert result["success"] is False
    assert "Docker daemon unavailable" in result["error"]


def test_execute_always_missing_image_errors():
    runner = SandboxRunner(llm_client=object(), use_docker="always")
    with patch.object(sr, "docker_available", return_value=True), \
         patch.object(sr, "docker_image_exists", return_value=False):
        used, result = runner._execute("print('x')", [], manifest=_dummy_manifest())
    assert result["success"] is False
    assert "not found" in result["error"]


def test_execute_auto_falls_back_when_no_docker():
    runner = SandboxRunner(llm_client=object(), use_docker="auto")
    with patch.object(sr, "docker_available", return_value=False), \
         patch.object(runner._local, "run_code", return_value={"success": True, "files": []}) as m:
        used, result = runner._execute("print('x')", [], manifest=_dummy_manifest())
    assert used == "local"
    m.assert_called_once()


# ── docker command construction ──────────────────────────────────────────

def test_docker_command_security_flags(tmp_path):
    runner = SandboxRunner(llm_client=object(), use_docker="never", memory_gb=3, cpus=1.5)
    cmd = runner._docker_command(str(tmp_path), skills_mounted=True)
    joined = " ".join(cmd)
    assert "--network none" in joined
    assert "--memory 3g" in joined
    assert "--pids-limit 512" in joined
    assert "no-new-privileges" in joined
    assert "--cpus 1.5" in joined
    assert "/work:/opt/gdpval" in joined  # mounted + baked skills both on path
    assert cmd[-3:] == ["python", "-u", "solution.py"]


def test_docker_command_pythonpath_without_mount(tmp_path):
    runner = SandboxRunner(llm_client=object(), use_docker="never")
    cmd = runner._docker_command(str(tmp_path), skills_mounted=False)
    idx = cmd.index("PYTHONPATH=/opt/gdpval")
    assert idx > 0


# ── end-to-end via local fallback ────────────────────────────────────────

def test_run_end_to_end_local_fallback():
    """Full run(): generate code (patched LLM) → execute locally → collect file."""
    code_block = (
        "Here is the solution.\n\n"
        "```python\n"
        "with open('result.txt', 'w') as f:\n"
        "    f.write('done')\n"
        "print('finished')\n"
        "```\n"
    )
    runner = SandboxRunner(llm_client=object(), use_docker="never")
    with _patch_complete(code_block):
        result = runner.run(
            task_prompt="Write the word done to a file",
            model="fake-model",
            reference_files=[],
            occupation="analyst",
        )
    assert result["success"] is True, result.get("error")
    assert "finished" in result["text"]
    filenames = [f["filename"] for f in result["files"]]
    assert "result.txt" in filenames
    # metadata reflects local executor + selection/resolution ran
    meta = result["metadata"]
    assert meta["executor"] == "local"
    assert meta["image"] is None
    assert "skills" in meta
    assert "dependencies" in meta


def test_run_no_code_returns_failure():
    runner = SandboxRunner(llm_client=object(), use_docker="never")
    with _patch_complete("I cannot help with that. No code here."):
        result = runner.run(
            task_prompt="Do something",
            model="fake-model",
            reference_files=[],
        )
    assert result["success"] is False
    assert "No Python code" in result["error"]
    assert result["metadata"]["executor"] == "none"


def test_run_selects_skills_for_video_task():
    code_block = "```python\nprint('ok')\n```"
    runner = SandboxRunner(llm_client=object(), use_docker="never")
    with _patch_complete(code_block):
        result = runner.run(
            task_prompt="Make a storyboard from the clip",
            model="fake-model",
            reference_files=["/tmp/does_not_exist_clip.mp4"],
        )
    assert result["success"] is True
    assert "video" in result["metadata"]["skills"]


# ── shared fixtures ──────────────────────────────────────────────────────

def _dummy_manifest():
    from core.dependency_resolver import DependencyManifest
    return DependencyManifest()
