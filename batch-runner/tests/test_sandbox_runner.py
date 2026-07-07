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


def _fake_run_factory(inspect_rc, ls_stdout, ls_rc=0):
    """Build a fake subprocess.run that distinguishes the inspect vs ls calls."""
    calls = []

    def _fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["docker", "image", "inspect"]:
            return SimpleNamespace(returncode=inspect_rc, stdout="", stderr="")
        if cmd[:3] == ["docker", "image", "ls"]:
            return SimpleNamespace(returncode=ls_rc, stdout=ls_stdout, stderr="")
        raise AssertionError(f"unexpected docker cmd: {cmd}")

    return _fake_run, calls


def test_docker_image_exists_falls_back_to_ls_under_containerd_store():
    # Reproduces the Docker Desktop containerd-store quirk: `image inspect
    # name:tag` fails with "No such image" but the tag IS present, so
    # `image ls -q` resolves it. The runner must still report the image present.
    fake_run, calls = _fake_run_factory(inspect_rc=1, ls_stdout="2df0878a9edf\n")
    with patch.object(sr.subprocess, "run", fake_run):
        assert docker_image_exists("gdpval-sandbox:latest") is True
    # It must have consulted the reliable ls fallback after inspect failed.
    assert any(c[:3] == ["docker", "image", "ls"] for c in calls)


def test_docker_image_exists_false_when_both_inspect_and_ls_empty():
    fake_run, _ = _fake_run_factory(inspect_rc=1, ls_stdout="")
    with patch.object(sr.subprocess, "run", fake_run):
        assert docker_image_exists("no-such-image:latest") is False


def test_docker_image_exists_fast_path_skips_ls_when_inspect_ok():
    fake_run, calls = _fake_run_factory(inspect_rc=0, ls_stdout="should-not-be-read")
    with patch.object(sr.subprocess, "run", fake_run):
        assert docker_image_exists("gdpval-sandbox:latest") is True
    # inspect succeeded → the ls fallback must not run.
    assert all(c[:3] != ["docker", "image", "ls"] for c in calls)


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


# ── output control loop: repair + manifest ───────────────────────────────

def _docx_bytes(text="content"):
    import io
    docx = pytest.importorskip("docx")
    buf = io.BytesIO()
    d = docx.Document()
    d.add_paragraph(text)
    d.save(buf)
    return buf.getvalue()


def _pptx_bytes():
    import io
    pptx = pytest.importorskip("pptx")
    buf = io.BytesIO()
    prs = pptx.Presentation()
    prs.slides.add_slide(prs.slide_layouts[6])
    prs.save(buf)
    return buf.getvalue()


def _runner_no_render(**kw):
    # Render off keeps the loop fast/hermetic; contract drives the repair.
    return SandboxRunner(
        llm_client=object(), use_docker="never",
        output_qa={"enabled": True, "render": False}, **kw
    )


def test_repair_loop_produces_repaired_ok():
    """Attempt 0 emits the wrong type, attempt 1 emits the right one."""
    _pptx = _pptx_bytes()
    _docx = _docx_bytes()
    runner = _runner_no_render()
    code = _fake_response("Deck.\n```python\nprint('build')\n```")
    exec_results = [
        ("local", {"success": True, "text": "r0",
                   "files": [{"filename": "deck.docx", "content": _docx}]}),
        ("local", {"success": True, "text": "r1",
                   "files": [{"filename": "deck.pptx", "content": _pptx}]}),
    ]
    with patch.object(sr, "complete", lambda **k: (code, {})), \
         patch.object(runner, "_execute", side_effect=exec_results):
        result = runner.run(task_prompt="Create a PowerPoint pptx deck for the board",
                            model="m", reference_files=[])

    assert result["final_status"] == "repaired_ok"
    assert result["qa_ok"] is True
    statuses = [a["status"] for a in result["metadata"]["attempts"]]
    assert statuses == ["failed_contract", "repaired_ok"]
    names = [f["filename"] for f in result["files"]]
    assert "deck.pptx" in names and "deck.docx" not in names


def test_clean_first_attempt_does_not_repair():
    _pptx = _pptx_bytes()
    runner = _runner_no_render()
    code = _fake_response("Deck.\n```python\nprint('build')\n```")
    mock_exec = patch.object(
        runner, "_execute",
        return_value=("local", {"success": True, "text": "ok",
                                "files": [{"filename": "deck.pptx", "content": _pptx}]}),
    )
    with patch.object(sr, "complete", lambda **k: (code, {})), mock_exec as m:
        result = runner.run(task_prompt="Create a pptx deck", model="m", reference_files=[])
    assert result["final_status"] == "ok"
    assert len(result["metadata"]["attempts"]) == 1
    m.assert_called_once()


def test_repair_disabled_runs_single_attempt():
    _docx = _docx_bytes()
    runner = SandboxRunner(
        llm_client=object(), use_docker="never",
        repair={"enabled": False},
        output_qa={"enabled": True, "render": False},
    )
    code = _fake_response("```python\nprint('x')\n```")
    with patch.object(sr, "complete", lambda **k: (code, {})), \
         patch.object(runner, "_execute",
                      return_value=("local", {"success": True, "text": "",
                                              "files": [{"filename": "out.docx", "content": _docx}]})):
        result = runner.run(task_prompt="Create a pptx deck", model="m", reference_files=[])
    assert len(result["metadata"]["attempts"]) == 1
    assert result["final_status"] == "failed_contract"
    # success still reflects that code executed and a file was produced.
    assert result["success"] is True


def test_failed_contract_after_repair_keeps_best():
    _docx = _docx_bytes()
    runner = _runner_no_render()
    code = _fake_response("```python\nprint('x')\n```")
    with patch.object(sr, "complete", lambda **k: (code, {})), \
         patch.object(runner, "_execute",
                      return_value=("local", {"success": True, "text": "",
                                              "files": [{"filename": "out.docx", "content": _docx}]})):
        result = runner.run(task_prompt="Create a pptx deck", model="m", reference_files=[])
    assert result["final_status"] == "failed_contract"
    assert len(result["metadata"]["attempts"]) == 2


def test_manifest_schema_present():
    _pptx = _pptx_bytes()
    runner = _runner_no_render()
    code = _fake_response("```python\nprint('x')\n```")
    with patch.object(sr, "complete", lambda **k: (code, {})), \
         patch.object(runner, "_execute",
                      return_value=("local", {"success": True, "text": "",
                                              "files": [{"filename": "deck.pptx", "content": _pptx}]})):
        result = runner.run(task_prompt="Create a pptx deck", model="m", reference_files=[])
    m = result["sandbox_manifest"]
    for key in ["schema_version", "execution_mode", "sandbox_backend", "selected_skills",
                "dependency_resolution", "dependency_import_probe", "deliverable_contract",
                "generated_artifacts", "verification_report", "attempts", "final_status"]:
        assert key in m, key
    assert m["execution_mode"] == "sandbox"
    assert m["final_status"] == "ok"
    # manifest.json is also emitted as a deliverable file.
    assert "manifest.json" in [f["filename"] for f in result["files"]]


def test_manifest_has_no_temp_paths():
    import json as _json
    _pptx = _pptx_bytes()
    runner = _runner_no_render()
    code = _fake_response("```python\nprint('x')\n```")
    with patch.object(sr, "complete", lambda **k: (code, {})), \
         patch.object(runner, "_execute",
                      return_value=("local", {"success": True, "text": "",
                                              "files": [{"filename": "deck.pptx", "content": _pptx}]})):
        result = runner.run(task_prompt="Create a pptx deck", model="m", reference_files=[])
    blob = _json.dumps(result["sandbox_manifest"])
    assert "gdpval_qa_" not in blob
    assert "/var/folders" not in blob and "/tmp/" not in blob


# ── import probe wiring (regression: probe was fed an empty list) ──────────

def _xlsx_bytes():
    import io
    openpyxl = pytest.importorskip("openpyxl")
    buf = io.BytesIO()
    openpyxl.Workbook().save(buf)
    return buf.getvalue()


def test_manifest_import_probe_reflects_resolved_deps():
    _xlsx = _xlsx_bytes()
    runner = _runner_no_render()
    code = _fake_response("```python\nprint('x')\n```")
    task = "Create an Excel xlsx workbook from data.xlsx"
    with patch.object(sr, "complete", lambda **k: (code, {})), \
         patch.object(runner, "_execute",
                      return_value=("local", {"success": True, "text": "",
                                              "files": [{"filename": "report.xlsx", "content": _xlsx}]})):
        result = runner.run(task_prompt=task, model="m", reference_files=["data.xlsx"])
    probe = result["sandbox_manifest"]["dependency_import_probe"]
    union = set(probe["available"]) | set(probe["missing"]) | set(probe["not_checked"])
    # Regression guard: the probe must reflect the resolved deps, not be empty.
    assert union, "import probe was empty — not wired to the resolved dependencies"
    # openpyxl is predicted from the .xlsx reference and installed in the test env.
    assert "openpyxl" in probe["available"]
    assert probe["env"] == "host"  # local execution probes the host interpreter


# ── tail redaction (regression: local crash leaked the temp path) ─────────

def test_sanitize_tail_redacts_and_trims():
    import os
    import tempfile
    from core.sandbox_runner import _sanitize_tail
    tmp = tempfile.gettempdir()
    redacted = _sanitize_tail(f'File "{tmp}/tmpABC/solution.py", line 3\nRuntimeError: boom')
    assert tmp not in redacted
    assert "<tmp>" in redacted
    assert "RuntimeError: boom" in redacted          # useful text preserved
    home = os.path.expanduser("~")
    assert home not in _sanitize_tail(f"opened {home}/secret/data.xlsx")
    assert _sanitize_tail("x" * 1000, limit=100) == "x" * 100   # trimming applied
    assert _sanitize_tail(None) == ""


def test_manifest_redacts_local_paths_on_real_crash():
    """Exercise the REAL local runner so the traceback embeds an absolute path."""
    import json as _json
    import os
    import tempfile
    runner = SandboxRunner(
        llm_client=object(), use_docker="never",
        output_qa={"enabled": True, "render": False}, repair={"enabled": False},
    )
    code = _fake_response("Build it.\n```python\nraise RuntimeError('boom from solution')\n```")
    with patch.object(sr, "complete", lambda **k: (code, {})):
        result = runner.run(task_prompt="Create a PDF report", model="m", reference_files=[])
    blob = _json.dumps(result["sandbox_manifest"])
    assert tempfile.gettempdir() not in blob
    assert "/var/folders" not in blob
    assert os.path.expanduser("~") not in blob
    # The error itself is preserved (redacted, not dropped).
    tail = result["sandbox_manifest"]["attempts"][0]["stderr_tail"]
    assert "RuntimeError" in tail and "<tmp>" in tail


# ── reasoning-effort / budget guard (PR #57 hardening) ───────────────────

def test_high_reasoning_low_budget_warns(capsys):
    """high reasoning + small code budget is the known empty-output/timeout trap."""
    SandboxRunner(
        llm_client=object(), use_docker="never",
        reasoning_effort="high", max_completion_tokens=16384,
    )
    out = capsys.readouterr().out
    assert "reasoning_effort='high'" in out
    assert "16384" in out
    assert str(sr.SAFE_HIGH_CODE_BUDGET) in out


def test_high_reasoning_safe_budget_no_warn(capsys):
    """At/above SAFE_HIGH_CODE_BUDGET, high reasoning must not warn."""
    SandboxRunner(
        llm_client=object(), use_docker="never",
        reasoning_effort="high", max_completion_tokens=sr.SAFE_HIGH_CODE_BUDGET,
    )
    assert "reasoning_effort='high'" not in capsys.readouterr().out


def test_medium_reasoning_low_budget_no_warn(capsys):
    """The guard is scoped to high effort; medium/low never warn."""
    SandboxRunner(
        llm_client=object(), use_docker="never",
        reasoning_effort="medium", max_completion_tokens=16384,
    )
    assert "reasoning_effort='high'" not in capsys.readouterr().out


def test_safe_high_code_budget_constant():
    assert sr.SAFE_HIGH_CODE_BUDGET == 32768
