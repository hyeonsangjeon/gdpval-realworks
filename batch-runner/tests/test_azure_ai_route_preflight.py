import importlib.util
import json
import os
import socket
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


BATCH_RUNNER = Path(__file__).resolve().parents[1]
SCRIPT = BATCH_RUNNER / "scripts" / "azure_ai_route_preflight.py"
REQUIREMENTS = BATCH_RUNNER / "requirements.txt"

SPEC = importlib.util.spec_from_file_location(
    "azure_ai_route_preflight",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


def _env(**updates: str) -> dict[str, str]:
    env = {
        "PATH": os.defpath,
        "PYTHONUTF8": "1",
    }
    env.update(updates)
    return env


def _direct_env(**updates: str) -> dict[str, str]:
    return _env(
        AZURE_AI_ROUTE_PROFILE="direct-v1",
        AZURE_OPENAI_V1_ENDPOINT=(
            "https://account.services.ai.azure.com/openai/v1/"
        ),
        **updates,
    )


def _run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=BATCH_RUNNER,
        env=env,
        check=False,
    )


def test_cli_emits_endpoint_and_deployment_free_route_records(tmp_path):
    output = tmp_path / "github-output.txt"
    direct = "https://account.services.ai.azure.com/openai/v1/"
    project = (
        "https://account.services.ai.azure.com/api/projects/project-one"
    )
    deployment = "private-deployment"

    result = _run(
        "--workload",
        f"narrative={deployment}",
        "--workload",
        f"code-interpreter={deployment}",
        env=_env(
            AZURE_AI_ROUTE_PROFILE="project-ci",
            AZURE_OPENAI_V1_ENDPOINT=direct,
            FOUNDRY_PROJECT_ENDPOINT=project,
            GITHUB_OUTPUT=str(output),
        ),
    )

    assert result.returncode == 0, result.stderr
    records = json.loads(result.stdout)
    assert [record["endpoint_kind"] for record in records] == [
        "direct-v1",
        "project",
    ]
    assert all(len(record["runtime_fingerprint"]) == 64 for record in records)
    output_lines = output.read_text(encoding="utf-8").splitlines()
    assert output_lines == [f"routes={result.stdout.strip()}"]
    emitted = result.stdout + output.read_text(encoding="utf-8")
    for private_value in (direct, project, deployment, "account", "project-one"):
        assert private_value not in emitted


def test_cli_rejects_deprecated_endpoint_without_echoing_it():
    endpoint = "https://private-account.openai.azure.com/"

    result = _run(
        "--workload",
        "inference=private-deployment",
        env=_direct_env(AZURE_OPENAI_ENDPOINT=endpoint),
    )

    assert result.returncode != 0
    assert "deprecated" in result.stderr
    assert endpoint not in result.stderr
    assert "private-account" not in result.stderr
    assert "private-deployment" not in result.stderr


@pytest.mark.parametrize(
    "name",
    preflight.FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV,
)
def test_cli_rejects_static_azure_credentials_without_echoing_values(name):
    endpoint = "https://account.services.ai.azure.com/openai/v1/"
    deployment = "private-deployment"
    secret = f"private-value-for-{name.lower()}"

    result = _run(
        "--workload",
        f"inference={deployment}",
        env=_env(
            AZURE_AI_ROUTE_PROFILE="direct-v1",
            AZURE_OPENAI_V1_ENDPOINT=endpoint,
            **{name: secret},
        ),
    )

    assert result.returncode != 0
    assert "static Azure credential" in result.stderr
    emitted = result.stdout + result.stderr
    assert secret not in emitted
    assert endpoint not in emitted
    assert deployment not in emitted


def test_cli_allows_federated_token_file_and_native_openai_key():
    result = _run(
        "--workload",
        "inference=private-deployment",
        env=_direct_env(
            AZURE_FEDERATED_TOKEN_FILE="/tmp/federated-token",
            OPENAI_API_KEY="native-provider-key",
        ),
    )

    assert result.returncode == 0, result.stderr
    emitted = result.stdout + result.stderr
    assert "federated-token" not in emitted
    assert "native-provider-key" not in emitted
    assert "private-deployment" not in emitted


def test_invalid_workload_fails_before_environment_resolution():
    endpoint = "https://private-account.openai.azure.com/"

    result = _run(
        "--workload",
        "unknown=private-deployment",
        env=_env(AZURE_OPENAI_ENDPOINT=endpoint),
    )

    assert result.returncode != 0
    assert "unsupported workload" in result.stderr
    assert "AZURE_AI_ROUTE_PROFILE" not in result.stderr
    assert "deprecated" not in result.stderr
    assert endpoint not in result.stderr
    assert "private-deployment" not in result.stderr


@pytest.mark.parametrize(
    ("encoded", "message"),
    [
        ("{broken", "invalid JSON"),
        ('{"not":"a-list"}', "must be a list of strings"),
    ],
)
def test_cli_rejects_malformed_workload_json(encoded, message):
    result = _run(
        env=_direct_env(AZURE_AI_WORKLOADS_JSON=encoded),
    )

    assert result.returncode != 0
    assert message in result.stderr
    assert encoded not in result.stderr


def test_cli_deduplicates_identical_workloads_from_args_and_environment():
    workload = "grader=private-deployment"

    result = _run(
        "--workload",
        workload,
        env=_direct_env(AZURE_AI_WORKLOADS_JSON=json.dumps([workload, workload])),
    )

    assert result.returncode == 0, result.stderr
    records = json.loads(result.stdout)
    assert len(records) == 1
    assert records[0]["workload"] == "grader"
    assert "private-deployment" not in result.stdout


def test_main_does_not_acquire_token_by_default(capsys):
    verifier = MagicMock()

    records = preflight.main(
        ["--workload", "inference=private-deployment"],
        env=_direct_env(),
        token_verifier=verifier,
    )

    verifier.assert_not_called()
    assert records[0]["workload"] == "inference"
    assert "private-deployment" not in capsys.readouterr().out


def test_main_verifies_token_only_when_explicitly_requested(capsys):
    verifier = MagicMock()

    preflight.main(
        [
            "--workload",
            "inference=private-deployment",
            "--verify-token",
        ],
        env=_direct_env(),
        token_verifier=verifier,
    )

    verifier.assert_called_once_with()
    assert "private-deployment" not in capsys.readouterr().out


def test_main_uses_route_specific_verifier_when_requested(monkeypatch):
    verifier = MagicMock()
    monkeypatch.setattr(preflight, "verify_route_tokens", verifier)

    preflight.main(
        [
            "--workload",
            "inference=private-deployment",
            "--verify-token",
        ],
        env=_direct_env(),
    )

    workloads, = verifier.call_args.args
    assert workloads == [
        (preflight.AzureAIWorkload.INFERENCE, "private-deployment")
    ]
    assert verifier.call_args.kwargs["settings"].profile.value == "direct-v1"


def test_token_verification_error_is_sanitized(capsys):
    verifier = MagicMock(
        side_effect=RuntimeError(
            "credential failed for https://private-account.openai.azure.com/ "
            "and private-deployment"
        )
    )

    with pytest.raises(SystemExit):
        preflight.main(
            [
                "--workload",
                "inference=private-deployment",
                "--verify-token",
            ],
            env=_direct_env(),
            token_verifier=verifier,
        )

    stderr = capsys.readouterr().err
    assert "Azure AI route token verification failed" in stderr
    assert "private-account" not in stderr
    assert "private-deployment" not in stderr


@pytest.mark.parametrize(
    "workload",
    [
        "inference=private\nroutes=owned",
        "inference=private\x1broutes=owned",
    ],
)
def test_cli_rejects_workload_control_injection_without_echo(workload):
    result = _run("--workload", workload, env=_direct_env())

    assert result.returncode != 0
    assert "control characters" in result.stderr
    assert "routes=owned" not in result.stderr
    assert "private" not in result.stderr


def test_github_output_rejects_symlink_target(tmp_path):
    target = tmp_path / "real-output.txt"
    target.write_text("existing=1\n", encoding="utf-8")
    output = tmp_path / "github-output.txt"
    output.symlink_to(target)

    result = _run(
        "--workload",
        "inference=private-deployment",
        env=_direct_env(GITHUB_OUTPUT=str(output)),
    )

    assert result.returncode != 0
    assert "regular non-symlink file" in result.stderr
    assert target.read_text(encoding="utf-8") == "existing=1\n"
    assert "private-deployment" not in result.stderr


def test_github_output_rejects_symlink_ancestor(tmp_path):
    real_directory = tmp_path / "real"
    real_directory.mkdir()
    linked_directory = tmp_path / "linked"
    linked_directory.symlink_to(real_directory, target_is_directory=True)

    result = _run(
        "--workload",
        "inference=private-deployment",
        env=_direct_env(GITHUB_OUTPUT=str(linked_directory / "output.txt")),
    )

    assert result.returncode != 0
    assert "non-symlink ancestors" in result.stderr
    assert not (real_directory / "output.txt").exists()


def test_github_output_appends_existing_file_in_one_append_write(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "github-output.txt"
    output.write_text("existing=1\n", encoding="utf-8")
    output.chmod(0o640)
    real_open = preflight.os.open
    real_write = preflight.os.write
    open_flags = []
    writes = []

    def recording_open(path, flags, mode=0o777, *, dir_fd=None):
        open_flags.append(flags)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    def recording_write(fd, payload):
        writes.append(payload)
        return real_write(fd, payload)

    monkeypatch.setattr(preflight.os, "open", recording_open)
    monkeypatch.setattr(preflight.os, "write", recording_write)

    preflight._append_github_output(
        str(output),
        '[{"workload":"grader"}]',
    )

    assert output.read_text(encoding="utf-8") == (
        'existing=1\nroutes=[{"workload":"grader"}]\n'
    )
    assert stat.S_IMODE(output.stat().st_mode) == 0o640
    assert len(writes) == 1
    assert open_flags[-1] & os.O_APPEND
    assert not open_flags[-1] & os.O_TRUNC


def test_github_output_created_file_has_mode_0600(tmp_path):
    output = tmp_path / "github-output.txt"

    preflight._append_github_output(str(output), "[]")

    assert output.read_text(encoding="utf-8") == "routes=[]\n"
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


@pytest.mark.parametrize("target_kind", ["directory", "fifo", "socket"])
def test_github_output_rejects_non_regular_target_types(tmp_path, target_kind):
    output = tmp_path / "github-output"
    unix_socket = None
    if target_kind == "directory":
        output.mkdir()
    elif target_kind == "fifo":
        os.mkfifo(output)
    else:
        unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        unix_socket.bind(str(output))

    try:
        with pytest.raises(ValueError, match="regular file"):
            preflight._append_github_output(str(output), "[]")
    finally:
        if unix_socket is not None:
            unix_socket.close()


@pytest.mark.parametrize(
    "raw_path",
    ["../output.txt", "nested/../output.txt", "output\nowned.txt"],
)
def test_github_output_rejects_parent_and_control_bearing_paths(raw_path):
    with pytest.raises(ValueError):
        preflight._absolute_output_path(raw_path)


def test_github_output_short_write_fails(tmp_path, monkeypatch):
    output = tmp_path / "github-output.txt"
    write = MagicMock(return_value=1)
    monkeypatch.setattr(preflight.os, "write", write)

    with pytest.raises(OSError, match="short write"):
        preflight._append_github_output(str(output), "[]")

    write.assert_called_once()


def test_github_output_missing_ancestor_error_is_sanitized(tmp_path):
    endpoint = "https://account.services.ai.azure.com/openai/v1/"
    deployment = "private-deployment"
    output = tmp_path / "missing" / "github-output.txt"

    result = _run(
        "--workload",
        f"inference={deployment}",
        env=_env(
            AZURE_AI_ROUTE_PROFILE="direct-v1",
            AZURE_OPENAI_V1_ENDPOINT=endpoint,
            GITHUB_OUTPUT=str(output),
        ),
    )

    assert result.returncode != 0
    assert "non-symlink ancestors" in result.stderr
    emitted = result.stdout + result.stderr
    assert endpoint not in emitted
    assert deployment not in emitted


def test_subprocess_environment_does_not_inherit_cloud_credentials(monkeypatch):
    monkeypatch.setenv("AZURE_CLIENT_ID", "real-client-id")
    monkeypatch.setenv("OPENAI_API_KEY", "real-provider-key")
    monkeypatch.setenv("HF_TOKEN", "real-hf-token")

    env = _env()

    assert "AZURE_CLIENT_ID" not in env
    assert "OPENAI_API_KEY" not in env
    assert "HF_TOKEN" not in env


@pytest.mark.parametrize(
    "requirement",
    [
        "openai==2.46.0",
        "azure-core==1.41.0",
        "azure-identity==1.25.3",
        "azure-ai-projects==2.3.0",
    ],
)
def test_sdk_requirement_is_exactly_pinned_once(requirement):
    package = requirement.partition("==")[0]
    matching = [
        line.strip()
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith(package)
    ]

    assert matching == [requirement]