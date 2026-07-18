"""Non-paid security tests for the agentic compute plane."""

from __future__ import annotations

import os
import json
import hashlib
import struct
import subprocess
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.agentic_compute import AgenticDockerBackend, _container_path
from core import agentic_verifier
from sandbox.agentic_image_prepare import _is_forbidden_executable


SECCOMP = Path(__file__).resolve().parent.parent / "sandbox" / "agentic-seccomp.json"
LAUNCHER = Path(__file__).resolve().parent.parent / "core" / "agentic_python_launcher.py"


def _backend(tmp_path, reference_files=None):
    return AgenticDockerBackend(
        task_prompt="Create report.txt",
        reference_files=list(reference_files or []),
        occupation="Analyst",
        image="gdpval-agentic-sandbox:test",
        seccomp_profile=str(SECCOMP),
        allow_unpinned_image=True,
        require_rootless_or_userns=False,
        require_approved_input_manifest=False,
        require_supply_chain_identity=False,
        require_dedicated_host=False,
    )


def test_task_container_command_has_hardening_flags(tmp_path):
    backend = _backend(tmp_path)
    try:
        command = backend._task_container_command()
        joined = " ".join(command)

        for required in (
            "--network none", "--ipc none", "--read-only",
            "--cap-drop ALL", "--pids-limit 128", "--ulimit nofile=256:256",
            "--user 65532:65532", "--security-opt no-new-privileges",
            "type=volume", "dst=/work", "volume-nocopy",
            "readonly", "bind-propagation=rprivate",
        ):
            assert required in joined
        assert "--pid host" not in joined
    finally:
        backend.close()


def test_outer_seccomp_is_default_deny_allowlist():
    profile = json.loads(SECCOMP.read_text(encoding="utf-8"))
    allowed = {
        name
        for rule in profile["syscalls"]
        if rule["action"] == "SCMP_ACT_ALLOW"
        for name in rule["names"]
    }

    assert profile["defaultAction"] == "SCMP_ACT_ERRNO"
    for denied in (
        "bpf", "mount", "setns", "unshare", "ptrace", "keyctl",
        "io_uring_setup", "userfaultfd", "process_vm_readv",
    ):
        assert denied not in allowed


@pytest.mark.parametrize(
    "name",
    [
        "gcc", "gcc-12", "x86_64-linux-gnu-gcc", "x86_64-linux-gnu-gcc-12",
        "g++-12", "x86_64-linux-gnu-ld.bfd", "as", "objcopy", "pip3.11",
    ],
)
def test_image_preparation_detects_versioned_and_prefixed_build_tools(name):
    assert _is_forbidden_executable(name) is True


def test_production_backend_requires_pinned_sbom_identity():
    with pytest.raises(ValueError, match="SBOM hash is required"):
        AgenticDockerBackend(
            task_prompt="task",
            reference_files=[],
            occupation="Analyst",
            image="image@sha256:" + "a" * 64,
            approved_input_manifest={},
        )


def test_substrate_manifest_is_condition_neutral(tmp_path):
    first = _backend(tmp_path)
    second = _backend(tmp_path)
    try:
        first.image_id = second.image_id = "sha256:" + "a" * 64
        first.verifier_image_id = second.verifier_image_id = "sha256:" + "a" * 64
        assert first.substrate_manifest() == second.substrate_manifest()
        serialized = json.dumps(first.substrate_manifest(), sort_keys=True)
        assert "baseline" not in serialized
        assert "treatment" not in serialized
    finally:
        first.close()
        second.close()


def test_verifier_image_components_are_hashed_from_actual_image_id(tmp_path):
    backend = _backend(tmp_path)
    expected = backend._component_hashes()
    commands = []

    def run(command, **_):
        commands.append(command)
        if command[1:3] == ["image", "inspect"]:
            output = json.dumps([{"Id": "sha256:" + "f" * 64}]).encode()
        else:
            output = json.dumps({
                "verifier": expected["verifier"],
                "capabilities": expected["capabilities"],
                "core_tree": expected["core_tree"],
                "sbom": backend.sbom_sha256,
            }).encode()
        return SimpleNamespace(returncode=0, stdout=output, stderr=b"")

    backend._run = run
    try:
        backend._verify_verifier_image_components()
    finally:
        backend.close()

    verifier_command = commands[1]
    assert "sha256:" + "f" * 64 in verifier_command
    assert verifier_command[verifier_command.index("--network") + 1] == "none"
    assert "--read-only" in verifier_command


def test_verifier_image_component_mismatch_fails_closed(tmp_path):
    backend = _backend(tmp_path)

    def run(command, **_):
        if command[1:3] == ["image", "inspect"]:
            output = json.dumps([{"Id": "sha256:" + "f" * 64}]).encode()
        else:
            output = json.dumps({
                "verifier": "0" * 64,
                "capabilities": "0" * 64,
                "core_tree": "0" * 64,
            }).encode()
        return SimpleNamespace(returncode=0, stdout=output, stderr=b"")

    backend._run = run
    try:
        with pytest.raises(RuntimeError, match="verifier image component"):
            backend._verify_verifier_image_components()
    finally:
        backend.close()


def test_production_verifier_image_sbom_mismatch_fails_closed(tmp_path):
    backend = _backend(tmp_path)
    backend.require_supply_chain_identity = True
    backend.sbom_sha256 = "a" * 64
    expected = backend._component_hashes()

    def run(command, **_):
        if command[1:3] == ["image", "inspect"]:
            output = json.dumps([{"Id": "sha256:" + "f" * 64}]).encode()
        else:
            output = json.dumps({
                "verifier": expected["verifier"],
                "capabilities": expected["capabilities"],
                "core_tree": expected["core_tree"],
                "sbom": "b" * 64,
            }).encode()
        return SimpleNamespace(returncode=0, stdout=output, stderr=b"")

    backend._run = run
    try:
        with pytest.raises(RuntimeError, match="SBOM identity mismatch"):
            backend._verify_verifier_image_components()
    finally:
        backend.close()


@pytest.mark.parametrize(
    "pid1_fds",
    [
        {"0": "/dev/null", "1": "pipe:[1]", "2": "pipe:[2]", "3": "/tmp/x"},
        {"0": "/dev/null", "1": "socket:[1]", "2": "pipe:[2]"},
    ],
)
def test_runtime_fd_probe_rejects_pid1_fd_or_socket(tmp_path, pid1_fds):
    backend = _backend(tmp_path)
    identity = {
        "uid": 65532,
        "gid": 65532,
        "groups": [],
        "probe_fds": {"0": "/dev/null", "1": "pipe:[1]", "2": "pipe:[2]"},
        "pid1_fds": pid1_fds,
    }
    backend._run = lambda *args, **kwargs: SimpleNamespace(
        returncode=0,
        stdout=json.dumps(identity).encode(),
        stderr=b"",
    )
    try:
        with pytest.raises(RuntimeError, match="pid1"):
            backend._verify_fds()
    finally:
        backend.close()


def test_input_staging_records_exact_hash_and_merkle_root(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("approved input", encoding="utf-8")
    backend = _backend(tmp_path, [source])
    try:
        backend._stage_inputs()

        assert len(backend.input_records) == 1
        assert backend.input_records[0]["model_path"] == "inputs/source.txt"
        assert len(backend.input_records[0]["sha256"]) == 64
        assert len(backend.input_merkle_root) == 64
        assert (backend.inputs_dir / "source.txt").read_bytes() == source.read_bytes()
        assert (backend.inputs_dir / "source.txt").stat().st_mode & 0o222 == 0
    finally:
        backend.close()


def test_input_staging_rejects_symlink_and_hardlink(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("input", encoding="utf-8")
    symlink = tmp_path / "link.txt"
    symlink.symlink_to(source)
    backend = _backend(tmp_path, [symlink])
    try:
        with pytest.raises(ValueError, match="input_type_or_link_violation"):
            backend._stage_inputs()
    finally:
        backend.close()


def test_input_staging_requires_exact_approved_manifest(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("approved input", encoding="utf-8")
    metadata = source.lstat()
    expected = {
        "documents/source.txt": {
            "path": "documents/source.txt",
            "type": "regular",
            "link_count": 1,
            "size_bytes": metadata.st_size,
            "source_allocated_bytes": metadata.st_blocks * 512,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "provider_classification": "approved_public_gdpval",
        }
    }
    backend = AgenticDockerBackend(
        task_prompt="Create report.txt",
        reference_files=[{
            "source_path": str(source),
            "relative_path": "documents/source.txt",
        }],
        occupation="Analyst",
        image="gdpval-agentic-sandbox:test",
        seccomp_profile=str(SECCOMP),
        allow_unpinned_image=True,
        require_rootless_or_userns=False,
        approved_input_manifest=expected,
        require_supply_chain_identity=False,
        require_dedicated_host=False,
    )
    try:
        backend._stage_inputs()
        assert backend.input_records[0]["sha256"] == expected[
            "documents/source.txt"
        ][
            "sha256"
        ]
        assert backend.input_records[0]["model_path"] == (
            "inputs/documents/source.txt"
        )
        assert backend.input_records[0]["staged_allocated_bytes"] > 0
    finally:
        backend.close()

    expected["documents/source.txt"]["sha256"] = "0" * 64
    backend = AgenticDockerBackend(
        task_prompt="Create report.txt",
        reference_files=[{
            "source_path": str(source),
            "relative_path": "documents/source.txt",
        }],
        occupation="Analyst",
        image="gdpval-agentic-sandbox:test",
        seccomp_profile=str(SECCOMP),
        allow_unpinned_image=True,
        require_rootless_or_userns=False,
        approved_input_manifest=expected,
        require_supply_chain_identity=False,
        require_dedicated_host=False,
    )
    try:
        with pytest.raises(ValueError, match="approved input identity mismatch"):
            backend._stage_inputs()
    finally:
        backend.close()

    hardlink = tmp_path / "hard.txt"
    os.link(source, hardlink)
    backend = _backend(tmp_path, [source])
    try:
        with pytest.raises(ValueError, match="input_type_or_link_violation"):
            backend._stage_inputs()
    finally:
        backend.close()


@pytest.mark.parametrize(
    ("path", "output"),
    [
        ("../escape", True),
        ("/etc/passwd", False),
        ("source.mov", False),
        ("inputs/source.mov", True),
        ("work/.hidden", True),
    ],
)
def test_container_path_rejects_escape_and_wrong_roots(path, output):
    with pytest.raises(ValueError):
        _container_path(path, output=output)


def test_ffmpeg_command_is_closed_and_shell_free(tmp_path):
    backend = _backend(tmp_path)
    try:
        command = backend._ffmpeg_command({
            "operation": "sample_frames",
            "input": "inputs/source.mp4",
            "output": "work/contact.png",
            "frame_count": 4,
            "width": 640,
            "start_seconds": 0,
            "duration_seconds": 10,
        })

        assert command[-1] == "/work/contact.png"
        assert "/usr/bin/ffmpeg" in command
        assert "-nostdin" in command
        assert "-n" in command
        assert command[command.index("-protocol_whitelist") + 1] == "file"
        assert not any(token in command for token in ("sh", "bash", "-c"))
        assert len([token for token in command if token == "/work/contact.png"]) == 1
        with pytest.raises(ValueError, match="unsupported ffmpeg input suffix"):
            backend._ffmpeg_command({
                "operation": "probe",
                "input": "inputs/playlist.m3u8",
            })
        with pytest.raises(ValueError, match="output extension"):
            backend._ffmpeg_command({
                "operation": "transcode_video",
                "input": "inputs/source.mov",
                "output": "work/report.webm",
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac",
                "width": 640,
                "height": 360,
                "fps": 24,
                "start_seconds": 0,
                "duration_seconds": 1,
            })
        with pytest.raises(ValueError, match="output extension"):
            backend._ffmpeg_command({
                "operation": "extract_audio",
                "input": "inputs/source.mov",
                "output": "work/report.flac",
                "format": "wav",
                "sample_rate": 16000,
                "channels": 1,
                "start_seconds": 0,
                "duration_seconds": 1,
            })
    finally:
        backend.close()


def test_ffprobe_returns_only_allowlisted_bounded_metadata(tmp_path):
    backend = _backend(tmp_path)
    backend.container_started = True
    backend._assert_pid1_only = lambda deadline=None: None
    backend._run_tool = lambda *args, **kwargs: subprocess.CompletedProcess(
        args[0],
        0,
        stdout=json.dumps({
            "format": {
                "filename": "/inputs/private-name.mov",
                "format_name": "mov,mp4",
                "duration": "1.250000",
                "tags": {"comment": "secret"},
            },
            "streams": [{
                "index": 0,
                "codec_name": "h264",
                "codec_type": "video",
                "width": 640,
                "height": 360,
                "tags": {"handler_name": "private"},
            }],
        }).encode(),
        stderr=b"",
    )
    try:
        result = backend.run_ffmpeg({
            "operation": "probe",
            "input": "inputs/source.mov",
        })
    finally:
        backend.container_started = False
        backend.close()

    assert result["ok"] is True
    assert result["data"]["metadata"] == {
        "format": {"duration": "1.250000", "format_name": "mov,mp4"},
        "streams": [{
            "codec_name": "h264",
            "codec_type": "video",
            "height": 360,
            "index": 0,
            "width": 640,
        }],
    }
    assert "private" not in json.dumps(result)


def test_verifier_rechecks_contract_on_exact_selected_deliverables(
    tmp_path, monkeypatch
):
    (tmp_path / "report.pdf").write_bytes(b"full-workspace-primary")
    (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")
    monkeypatch.setattr(agentic_verifier, "SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setattr(
        agentic_verifier,
        "run_output_qa",
        lambda *args, **kwargs: SimpleNamespace(
            ok=True,
            render_reports=[],
            blocking_errors=[],
            warnings=[],
        ),
    )

    result = agentic_verifier.verify({
        "task_prompt": "Create a PDF report",
        "reference_hashes": [],
        "selected_deliverables": ["notes.txt"],
    })

    assert result["ok"] is False
    assert result["error_type"] == "artifact_verification_failed"
    assert result["data"]["artifact_count"] == 1
    assert result["data"]["artifacts"][0]["path"] == "notes.txt"


def test_tool_output_is_bounded_before_host_memory_capture():
    result = AgenticDockerBackend._run_tool(
        [sys.executable, "-c", "import sys;sys.stdout.write('x' * 1000000)"],
        timeout=10,
    )

    assert len(result.stdout) <= 32768
    assert result.returncode != 0


@pytest.mark.skipif(sys.platform != "linux", reason="libseccomp launcher is Linux-only")
def test_generated_python_launcher_denies_exec_and_network():
    source = b"""
import os
import socket

denied = []
for action in (
    lambda: os.system('/bin/true'),
    lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM),
):
    try:
        action()
    except OSError as exc:
        denied.append(exc.errno)
assert len(denied) == 2, denied
print('blocked')
"""
    harness = (
        "import sys;"
        "from core.agentic_python_launcher import _install_filter;"
        "code=compile(sys.stdin.buffer.read(),'<security-test>','exec');"
        "_install_filter();exec(code,{'__name__':'__main__'})"
    )
    result = subprocess.run(
        [sys.executable, "-c", harness],
        input=source,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
        cwd=Path(__file__).resolve().parent.parent,
    )
    if b"seccomp TSYNC unavailable" in result.stderr:
        pytest.skip("host runtime does not expose seccomp TSYNC; Docker gate remains required")
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stdout.strip() == b"blocked"


@pytest.mark.integration
def test_agentic_docker_backend_end_to_end(tmp_path):
    image = os.environ.get(
        "AGENTIC_TEST_IMAGE", "gdpval-agentic-sandbox:local"
    )
    inspect = subprocess.run(
        ["docker", "image", "inspect", image],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if inspect.returncode != 0:
        pytest.skip(f"agentic test image is unavailable: {image}")

    source = tmp_path / "input.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(struct.pack("<h", 0) * 16000)
    backend = AgenticDockerBackend(
        task_prompt="Create a professional WAV audio report named report.wav",
        reference_files=[str(source)],
        occupation="Analyst",
        image=image,
        seccomp_profile=str(SECCOMP),
        allow_unpinned_image=True,
        require_rootless_or_userns=False,
        require_approved_input_manifest=False,
        require_supply_chain_identity=False,
        require_dedicated_host=False,
        enforce_cpu_limit=False,
        enforce_pid_limit=False,
        enforce_outer_seccomp=False,
        enforce_procfs_policy=False,
        local_root_parent=os.environ.get("AGENTIC_TEST_LOCAL_ROOT_PARENT"),
        docker_root_parent=os.environ.get("AGENTIC_TEST_DOCKER_ROOT_PARENT"),
    )
    container_name = backend.container_name
    try:
        startup = backend.start()
        assert startup["ok"] is True, startup
        assert startup["data"]["input_count"] == 1
        assert len(startup["data"]["input_merkle_root"]) == 64
        assert backend.inspect_environment()["ok"] is True

        first = backend.run_ffmpeg({
            "operation": "extract_audio",
            "input": "inputs/input.wav",
            "output": "work/stage.flac",
            "format": "flac",
            "sample_rate": 16000,
            "channels": 1,
            "start_seconds": 0,
            "duration_seconds": 0.5,
        })
        assert first["ok"] is True, first
        workspace = backend.inspect_workspace()
        assert workspace["ok"] is True, workspace
        assert any(
            item["path"] == "work/stage.flac"
            for item in workspace["data"]["work"]
        )

        second = backend.run_ffmpeg({
            "operation": "transcode_audio",
            "input": "work/stage.flac",
            "output": "work/report.wav",
            "format": "wav",
            "sample_rate": 16000,
            "channels": 1,
            "start_seconds": 0,
            "duration_seconds": 0.4,
        })
        assert second["ok"] is True, second

        inspection = backend.inspect_artifacts()
        assert inspection["ok"] is True, inspection
        assert inspection["data"]["artifact_count"] >= 2

        finalized = backend.finalize(
            ["report.wav"], "Verified professional audio report"
        )
        assert finalized["ok"] is True, finalized
        result = backend.best_result()
        assert result is not None and result["success"] is True
        assert len(result["files"]) == 1
        assert result["files"][0]["filename"] == "report.wav"
        assert len(result["files"][0]["content"]) > 44
    finally:
        backend.close()

    remaining = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name=^{container_name}$", "-q"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    assert remaining.stdout.strip() == ""


@pytest.mark.integration
def test_agentic_docker_generated_python_denies_exec_and_network(tmp_path):
    image = os.environ.get(
        "AGENTIC_TEST_IMAGE", "gdpval-agentic-sandbox:local"
    )
    source = tmp_path / "input.txt"
    source.write_text("approved input", encoding="utf-8")
    backend = AgenticDockerBackend(
        task_prompt="Create report.txt",
        reference_files=[str(source)],
        occupation="Analyst",
        image=image,
        seccomp_profile=str(SECCOMP),
        allow_unpinned_image=True,
        require_rootless_or_userns=False,
        require_approved_input_manifest=False,
        require_supply_chain_identity=False,
        require_dedicated_host=False,
        enforce_cpu_limit=False,
        enforce_pid_limit=False,
        enforce_outer_seccomp=False,
        enforce_procfs_policy=False,
        local_root_parent=os.environ.get("AGENTIC_TEST_LOCAL_ROOT_PARENT"),
        docker_root_parent=os.environ.get("AGENTIC_TEST_DOCKER_ROOT_PARENT"),
    )
    try:
        startup = backend.start()
        assert startup["ok"] is True, startup
        result = backend.run_python(
            """
from pathlib import Path
import socket
import subprocess
blocked = 0
for action in (
    lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM),
    lambda: subprocess.run(['/usr/bin/ffprobe', '-version']),
):
    try:
        action()
    except OSError:
        blocked += 1
assert blocked == 2, blocked
Path('report.txt').write_text('blocked')
""",
            30,
        )
        if "seccomp TSYNC unavailable" in result.get("data", {}).get(
            "stderr_tail", ""
        ):
            pytest.skip(
                "local kernel lacks seccomp TSYNC; generated Python stayed fail-closed"
            )
        assert result["ok"] is True, result
    finally:
        backend.close()


@pytest.mark.integration
def test_agentic_production_runner_preflight(tmp_path):
    if os.environ.get("AGENTIC_PRODUCTION_PREFLIGHT") != "1":
        pytest.skip("dedicated production runner preflight not requested")
    image = os.environ["AGENTIC_PRODUCTION_IMAGE"]
    sbom_sha256 = os.environ["AGENTIC_PRODUCTION_SBOM_SHA256"]
    apparmor_profile = os.environ["AGENTIC_PRODUCTION_APPARMOR_PROFILE"]
    if "@sha256:" not in image:
        pytest.fail("production image must be digest-pinned")
    source = tmp_path / "source.txt"
    source.write_text("approved public fixture", encoding="utf-8")

    probe = AgenticDockerBackend(
        task_prompt="Create report.txt",
        reference_files=[str(source)],
        occupation="Analyst",
        image=image,
        verifier_image=image,
        apparmor_profile=apparmor_profile,
        sbom_sha256=sbom_sha256,
        allow_unpinned_image=False,
        require_rootless_or_userns=True,
        require_approved_input_manifest=False,
        require_supply_chain_identity=True,
        require_dedicated_host=True,
    )
    try:
        probe._stage_inputs()
        record = probe.input_records[0]
        expected_root = probe.input_merkle_root
        approved = {
            record["path"]: {
                key: record[key]
                for key in (
                    "path", "type", "link_count", "size_bytes",
                    "source_allocated_bytes", "sha256",
                    "provider_classification",
                )
            }
        }
    finally:
        probe.close()

    backend = AgenticDockerBackend(
        task_prompt="Create report.txt",
        reference_files=[{
            "source_path": str(source),
            "relative_path": "source.txt",
        }],
        occupation="Analyst",
        image=image,
        verifier_image=image,
        apparmor_profile=apparmor_profile,
        sbom_sha256=sbom_sha256,
        approved_input_manifest=approved,
        expected_input_merkle_root=expected_root,
    )
    container_name = backend.container_name
    volume_name = backend.work_volume_name
    try:
        startup = backend.start()
        assert startup["ok"] is True, startup
        result = backend.run_python(
            """
from pathlib import Path
import socket
import subprocess
blocked = 0
for action in (
    lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM),
    lambda: subprocess.run(['/usr/bin/ffprobe', '-version']),
):
    try:
        action()
    except OSError:
        blocked += 1
assert blocked == 2, blocked
Path('report.txt').write_text('verified production preflight')
""",
            30,
        )
        assert result["ok"] is True, result
        inspection = backend.inspect_artifacts()
        assert inspection["ok"] is True, inspection
        finalized = backend.finalize(
            ["report.txt"], "production preflight"
        )
        assert finalized["ok"] is True, finalized
    finally:
        backend.close()

    assert subprocess.run(
        ["docker", "container", "inspect", container_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode != 0
    assert subprocess.run(
        ["docker", "volume", "inspect", volume_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode != 0