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

def _fake_response(content: str, usage=None):
    """Build a minimal object shaped like an OpenAI chat completion."""
    msg = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice], usage=usage)


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
    assert result["error_category"] == "backend_unavailable"
    assert result["preflight"] is None


def test_execute_always_missing_image_errors():
    runner = SandboxRunner(llm_client=object(), use_docker="always")
    with patch.object(sr, "docker_available", return_value=True), \
         patch.object(sr, "docker_image_exists", return_value=False):
        used, result = runner._execute("print('x')", [], manifest=_dummy_manifest())
    assert result["success"] is False
    assert "not found" in result["error"]
    assert result["error_category"] == "backend_unavailable"


def test_backend_unavailable_manifest_is_not_executed():
    runner = SandboxRunner(
        llm_client=object(),
        use_docker="always",
        repair={"enabled": False},
        output_qa={"enabled": True, "render": False},
    )
    response = _fake_response("```python\nprint('x')\n```")

    with patch.object(sr, "complete", lambda **kwargs: (response, {})), \
         patch.object(sr, "docker_available", return_value=False):
        result = runner.run(
            task_prompt="Create a PDF report",
            model="m",
            reference_files=[],
        )

    assert result["error_category"] == "backend_unavailable"
    assert result["sandbox_manifest"]["sandbox_backend"] == "not_executed"
    assert result["sandbox_manifest"]["attempts"][0]["error_category"] == "backend_unavailable"


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
    with patch.object(sr.os, "getuid", return_value=1234, create=True), \
         patch.object(sr.os, "getgid", return_value=5678, create=True):
        cmd = runner._docker_command(str(tmp_path), skills_mounted=True)
    joined = " ".join(cmd)
    assert "--network none" in joined
    assert "--memory 3g" in joined
    assert "--pids-limit 512" in joined
    assert "no-new-privileges" in joined
    assert "--user 1234:5678" in joined
    assert "--cpus 1.5" in joined
    assert "/work:/opt/gdpval" in joined  # mounted + baked skills both on path
    # Prevent root-owned __pycache__ in the bind-mounted tmpdir (host rmtree EPERM).
    assert "PYTHONDONTWRITEBYTECODE=1" in joined
    assert cmd[-4:] == [runner.image, "python", "-u", sr.RUNNER_FILENAME]


def test_docker_command_without_posix_ids_omits_user(tmp_path):
    runner = SandboxRunner(llm_client=object(), use_docker="never")
    with patch.object(sr.os, "getuid", None, create=True), \
         patch.object(sr.os, "getgid", None, create=True):
        cmd = runner._docker_command(str(tmp_path), skills_mounted=False)
    assert "--user" not in cmd
    assert cmd[-4:] == [runner.image, "python", "-u", sr.RUNNER_FILENAME]


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
    assert result["sandbox_manifest"]["sandbox_backend"] == "not_executed"
    assert len(result["sandbox_manifest"]["attempts"]) == 1
    assert result["sandbox_manifest"]["attempts"][0]["error_category"] == "no_code"
    assert result["sandbox_manifest"]["attempts"][0]["response"]["sha256"]


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
    video = next(
        skill for skill in result["sandbox_manifest"]["selected_skills_detail"]
        if skill["name"] == "video"
    )
    assert video["score"] > 0
    assert ".mp4" in video["matched_extensions"]


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


def test_syntax_preflight_skips_execution_then_repairs():
    """Invalid Python never executes; one guided regeneration can recover."""
    _pptx = _pptx_bytes()
    runner = _runner_no_render()
    responses = [
        _fake_response('```python\ncontent = """unterminated\n```'),
        _fake_response("```python\nprint('build')\n```"),
    ]
    prompts = []

    def _complete(**kwargs):
        prompts.append(kwargs["messages"][1]["content"])
        return responses[len(prompts) - 1], {}

    with patch.object(sr, "complete", _complete), \
         patch.object(
             runner,
             "_execute",
             side_effect=[
                 (
                     "local",
                     {
                         "success": False,
                         "text": "",
                         "files": [],
                         "error": "SyntaxError at line 1",
                         "error_category": "syntax_error",
                         "preflight": {
                             "ok": False,
                             "stage": "compile",
                             "error_type": "SyntaxError",
                             "line": 1,
                             "offset": 11,
                             "target_python": "3.11.15",
                         },
                     },
                 ),
                 (
                     "local",
                     {
                         "success": True,
                         "text": "ok",
                         "files": [{"filename": "deck.pptx", "content": _pptx}],
                         "preflight": {
                             "ok": True,
                             "stage": "compile",
                             "target_python": "3.11.15",
                         },
                     },
                 ),
             ],
         ) as execute:
        result = runner.run(
            task_prompt="Create a pptx deck",
            model="m",
            reference_files=[],
        )

    assert execute.call_count == 2
    attempts = result["sandbox_manifest"]["attempts"]
    assert [attempt["executor"] for attempt in attempts] == ["local", "local"]
    assert attempts[0]["blocking_error_categories"] == ["syntax_error"]
    assert attempts[0]["preflight"]["error_type"] == "SyntaxError"
    assert attempts[1]["preflight"]["ok"] is True
    assert result["final_status"] == "repaired_ok"
    assert "Required repair strategy:" in prompts[1]
    assert "validate it with compile" in prompts[1]


def test_terminal_syntax_preflight_records_not_executed_backend():
    runner = _runner_no_render(repair={"enabled": False})
    response = _fake_response('```python\nvalue = """unterminated\n```')

    with patch.object(sr, "complete", lambda **kwargs: (response, {})), \
         patch.object(
             runner,
             "_execute",
             return_value=(
                 "local",
                 {
                     "success": False,
                     "text": "",
                     "files": [],
                     "error": "SyntaxError at line 1",
                     "error_category": "syntax_error",
                     "preflight": {
                         "ok": False,
                         "stage": "compile",
                         "error_type": "SyntaxError",
                         "line": 1,
                         "offset": 9,
                         "target_python": "3.11.15",
                     },
                 },
             ),
         ) as execute:
        result = runner.run(
            task_prompt="Create a PDF report",
            model="m",
            reference_files=[],
        )

    execute.assert_called_once()
    assert result["sandbox_manifest"]["sandbox_backend"] == "not_executed"
    assert result["sandbox_manifest"]["attempts"][0]["preflight"]["ok"] is False


def test_local_preflight_uses_actual_host_interpreter():
    import sys

    runner = _runner_no_render()
    code = "try:\n    raise ValueError('x')\nexcept* ValueError:\n    pass\n"

    result = runner._local.run_code(code)

    expected_version = ".".join(map(str, sys.version_info[:3]))
    assert result["preflight"]["target_python"] == expected_version
    assert result["preflight"]["ok"] is (sys.version_info >= (3, 11))


def test_local_preflight_catches_compile_stage_error():
    runner = _runner_no_render()

    result = runner._local.run_code("return 1")

    assert result["preflight"]["ok"] is False
    assert result["preflight"]["stage"] == "compile"
    assert result["preflight"]["error_type"] == "SyntaxError"


@pytest.mark.skipif(
    not sr.docker_available() or not sr.docker_image_exists(sr.DEFAULT_SANDBOX_IMAGE),
    reason="gdpval sandbox image unavailable",
)
def test_docker_preflight_uses_python_311_and_rejects_312_syntax():
    py311 = "try:\n    raise ValueError('x')\nexcept* ValueError:\n    pass\n"

    def run_launcher(source):
        from core.subprocess_runner import (
            RUNNER_FILENAME,
            build_execution_launcher,
            parse_execution_streams,
        )

        launcher = build_execution_launcher([])
        harness = (
            "from pathlib import Path\n"
            "import runpy\n"
            f"Path('solution.py').write_text({source!r}, encoding='utf-8')\n"
            f"Path({RUNNER_FILENAME!r}).write_text({launcher!r}, encoding='utf-8')\n"
            "try:\n"
            f"    runpy.run_path({RUNNER_FILENAME!r}, run_name='__main__')\n"
            "except SyntaxError:\n"
            "    pass\n"
        )
        completed = sr.subprocess.run(
            [
                "docker", "run", "--rm", sr.DEFAULT_SANDBOX_IMAGE,
                "python", "-c", harness,
            ],
            capture_output=True,
            text=False,
            timeout=60,
        )
        _, stderr, preflight, _ = parse_execution_streams(
            completed.stdout,
            completed.stderr,
        )
        assert completed.returncode == 0, stderr
        return preflight

    accepted = run_launcher(py311)
    rejected = run_launcher("type Alias = int")

    assert accepted["ok"] is True
    assert accepted["target_python"].startswith("3.11.")
    assert rejected["ok"] is False
    assert rejected["target_python"].startswith("3.11.")


def test_runtime_failure_beats_prior_preflight_failure_as_best_attempt():
    runner = _runner_no_render()
    responses = [
        _fake_response('```python\nvalue = """unterminated\n```'),
        _fake_response("```python\nraise RuntimeError('runtime failure')\n```"),
    ]
    calls = 0

    def _complete(**kwargs):
        nonlocal calls
        response = responses[calls]
        calls += 1
        return response, {}

    with patch.object(sr, "complete", _complete), \
         patch.object(
             runner,
             "_execute",
             side_effect=[
                 (
                     "local",
                     {
                         "success": False,
                         "text": "",
                         "files": [],
                         "error": "SyntaxError at line 1",
                         "error_category": "syntax_error",
                         "preflight": {
                             "ok": False,
                             "stage": "compile",
                             "error_type": "SyntaxError",
                             "line": 1,
                             "offset": 9,
                             "target_python": "3.11.15",
                         },
                     },
                 ),
                 (
                     "local",
                     {
                         "success": False,
                         "text": "",
                         "files": [],
                         "error": "RuntimeError: runtime failure",
                         "error_category": "execution_error",
                         "preflight": {
                             "ok": True,
                             "stage": "compile",
                             "target_python": "3.11.15",
                         },
                     },
                 ),
             ],
         ) as execute:
        result = runner.run(
            task_prompt="Create a PDF report",
            model="m",
            reference_files=[],
        )

    assert execute.call_count == 2
    assert result["sandbox_manifest"]["best_attempt"] == 1
    assert result["sandbox_manifest"]["sandbox_backend"] == "local_fallback"
    assert result["sandbox_manifest"]["final_status"] == "failed_execution"
    assert result["error_category"] == "execution_error"


def test_docker_oom_returns_structured_category():
    runner = _runner_no_render()
    completed = SimpleNamespace(returncode=137, stdout="", stderr="")

    with patch.object(sr.subprocess, "run", return_value=completed):
        result = runner._execute_docker("print('x')", [])

    assert result["error_category"] == "out_of_memory"
    assert result["error"].startswith("memory_error:")


def test_docker_binary_decode_failure_returns_structured_category():
    runner = _runner_no_render()
    decode_error = UnicodeDecodeError("utf-8", b"\xa9", 0, 1, "invalid")

    with patch.object(sr.subprocess, "run", side_effect=decode_error):
        result = runner._execute_docker("print('x')", [])

    assert result["error_category"] == "binary_decode_error"
    assert "not valid UTF-8" in result["error"]


@pytest.mark.parametrize(
    "stderr",
    [
        "Traceback (most recent call last):\nOSError: [Errno 12] Cannot allocate memory\n",
        "Traceback (most recent call last):\nRuntimeError: CUDA out of memory\n",
    ],
)
def test_docker_runtime_oom_message_uses_structured_category(stderr):
    from core.subprocess_runner import PREFLIGHT_PREFIX

    runner = _runner_no_render()
    protocol = (
        PREFLIGHT_PREFIX
        + '{"ok":true,"stage":"compile","target_python":"3.11.15"}\n'
    )
    completed = SimpleNamespace(
        returncode=1,
        stdout=b"",
        stderr=(protocol + stderr).encode("utf-8"),
    )

    with patch.object(sr.subprocess, "run", return_value=completed):
        result = runner._execute_docker("print('x')", [])

    assert result["error_category"] == "out_of_memory"
    assert result["preflight"]["ok"] is True


@pytest.mark.parametrize(
    ("error", "category", "guidance"),
    [
        (
            "KeyError: 'Invoice Date'",
            "schema_error",
            "Inspect the actual sheets, header rows, column names",
        ),
        (
            "AttributeError: object has no attribute add_hyperlink",
            "api_compatibility",
            "Verify the installed library's supported API",
        ),
        (
            "UnicodeDecodeError: utf-8 codec cannot decode byte 0xa9",
            "binary_decode_error",
            "Capture subprocess and media-tool output as bytes",
        ),
        (
            "OutOfMemoryError: Failed to allocate 24883200 bytes",
            "out_of_memory",
            "Switch to streaming or chunked processing",
        ),
    ],
)
def test_reflection_uses_exception_specific_guidance(error, category, guidance):
    from core.deliverable_contract import infer_deliverable_contract

    runner = _runner_no_render()
    contract = infer_deliverable_contract("Create a PDF report", [], {})
    blocking = [f"execution_failed: {error}"]

    reflection = runner._build_reflection(
        contract,
        blocking,
        code="print('x')",
        result={"text": "", "error": error},
        analysis={"warnings": []},
    )

    assert sr._blocking_error_categories(blocking) == [category]
    assert guidance in reflection


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
    for key in ["schema_version", "execution_mode", "sandbox_backend", "sandbox_image",
                "run_context",
                "selected_skills", "selected_skills_detail",
                "dependency_resolution", "dependency_import_probe", "deliverable_contract",
                "generated_artifacts", "verification_report", "attempts", "best_attempt",
                "final_status"]:
        assert key in m, key
    assert m["execution_mode"] == "sandbox"
    assert m["final_status"] == "ok"
    assert m["sandbox_image"] is None
    assert isinstance(m["run_context"], dict)
    assert m["best_attempt"] == 0
    assert len(m["attempts"][0]["prompt_sha256"]) == 64
    assert "usage" in m["attempts"][0]
    assert "llm_latency_ms" in m["attempts"][0]
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
    """Persist only a fingerprint/category for a real local crash."""
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
    attempt = result["sandbox_manifest"]["attempts"][0]
    assert attempt["error_category"] == "execution_error"
    assert attempt["stderr"]["chars"] > 0
    assert len(attempt["stderr"]["sha256"]) == 64
    assert "RuntimeError" not in blob
    assert "boom from solution" not in blob


def test_manifest_never_persists_sensitive_process_text():
    import json as _json
    secret = "token=super-sensitive-value /arbitrary/private/input.csv"
    runner = _runner_no_render(repair={"enabled": False})
    response = _fake_response("```python\nprint('x')\n```")
    with patch.object(sr, "complete", lambda **k: (response, {})), \
         patch.object(runner, "_execute", return_value=(
             "local",
             {"success": False, "text": secret, "error": secret, "files": []},
         )):
        result = runner.run(task_prompt="Create a PDF", model="m", reference_files=[])

    blob = _json.dumps(result["sandbox_manifest"])
    assert secret not in blob
    assert "super-sensitive-value" not in blob
    attempt = result["sandbox_manifest"]["attempts"][0]
    assert attempt["stdout"]["chars"] == len(secret)
    assert attempt["stderr"]["chars"] == len(secret)


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
