"""One source-only proof: real local Git and validators, synthetic refusals.

No input preparation, provider call, reservation or launch verdict is stubbed
as successful. The test consumes no study cell and authorizes no live run.
"""

import hashlib
import io
import json
import socket
import subprocess
import tarfile
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import gpt54_disposable_checkout as checkout
import gpt54_v2_grading_input as reader
import gpt56_foundry_evidence_intake as evidence
import gpt56_pilot_identity_plan as identity
import gpt56_pilot_input_capture as capture
import gpt56_pilot_wire_receipt as wire
import gpt56_sol_codex_pilot_preflight as pilot
import step8_grade as step8
from core import azure_ai_clients, codex_azure_token


CANARY = "Bearer PRIVATE-source-canary-DO-NOT-PUBLISH"


def test_sol_source_registration(tmp_path, monkeypatch, capsys):
    root = Path(__file__).resolve().parents[2]
    assert pilot.ROOT == root
    original = pilot.load_plan(root / pilot.ACTIVE_PLAN)
    profile_path = root / pilot.SOURCE_PROFILE
    profile_data = profile_path.read_bytes()
    profile = pilot.load_plan(profile_path)
    plan_sha = pilot.seal(profile)
    previous_path = root / pilot.SOURCE_PROFILE_PREVIOUS
    previous_bytes = previous_path.read_bytes()
    previous = pilot.load_plan(previous_path)
    assert pilot.SOURCE_PROFILE.endswith("_source_20261025.yaml")
    assert pilot.SOURCE_PROFILE_PREVIOUS.endswith("_source_20261023.yaml")
    assert hashlib.sha256(previous_bytes).hexdigest() == (
        pilot.SOURCE_PROFILE_PREVIOUS_SHA256
    ) == "506de35370ffe6d54e6decb2459a4f4abda47136d550c010086b0fffd5c1e482"
    assert {name for name, digest in profile["source_pins"].items()
            if digest != previous["source_pins"][name]} == pilot.SOURCE_PROFILE_DELTA == {
        "batch-runner/core/codex_runner.py", "batch-runner/step2_run_inference.py",
        "batch-runner/gpt56_pilot_wire_receipt.py", "batch-runner/gpt56_pilot_runtime_caps_usage.py",
        "batch-runner/gpt56_sol_codex_pilot_preflight.py",
    }
    assert {k: v for k, v in profile.items() if k != "source_pins"} == {
        k: v for k, v in previous.items() if k != "source_pins"
    }
    shared = root / "batch-runner/gpt54_disposable_checkout.py"
    assert hashlib.sha256(shared.read_bytes()).hexdigest() == next(iter(pilot.SOURCE_PROFILE_AUXILIARY.values()))
    assert hashlib.sha256((root / pilot.ACTIVE_PLAN).read_bytes()).hexdigest() == pilot.FOUNDRY_PLAN_SHA256
    assert {k: v for k, v in profile.items() if k != "source_pins"} == {
        k: v for k, v in original.items() if k != "source_pins"
    }

    forbidden_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        raise AssertionError(CANARY)

    real_popen = subprocess.Popen
    git_commands = []

    def only_local_git(command, *args, **kwargs):
        assert isinstance(command, list) and command[0] == "/usr/bin/git"
        index = command.index("-C")
        assert command[index + 1] == str(root)
        assert command[index + 2] in {"rev-parse", "status", "archive"}
        assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == ""
        assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        git_commands.append(command[index + 2])
        return real_popen(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", only_local_git)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    for module in (azure_ai_clients, codex_azure_token):
        monkeypatch.setattr(module, "DefaultAzureCredential", forbidden)
        monkeypatch.setattr(module, "get_bearer_token_provider", forbidden)
    for name in ("OpenAI", "AzureOpenAI", "AzureAIClientFactory"):
        # Preserve classes used in evaluated annotations during imports.
        monkeypatch.setattr(getattr(azure_ai_clients, name), "__init__", forbidden)
    monkeypatch.setattr(step8.Grader, "__init__", forbidden)
    monkeypatch.setattr(codex_azure_token, "acquire_token", forbidden)
    for module, name in (
        (evidence, "publish_foundry_evidence"), (identity, "publish_pilot_identity"),
        (capture, "prepare_pilot_inputs"), (capture, "write_pilot_prepared_and_capture"),
        (checkout, "materialize_run_config_bundle"), (checkout, "materialize_run_input_bundle"),
    ):
        monkeypatch.setattr(module, name, forbidden)

    # Only read the sealed draft: no budget owner, observer, listener or claim.
    assert wire._native_caps() == {
        "per_attempt": {"native_model_calls": 32, "input_tokens": 300000,
                        "output_tokens": 10000, "wall_clock_seconds": 1800},
        "per_task": {"native_model_calls": 128},
        "per_pilot": {"native_model_calls": 640},
    }

    head = checkout._git(root, "rev-parse", "--verify", "HEAD^{commit}").stdout.decode().strip()
    options = {"expected_plan_sha256": plan_sha, "reviewed_source_sha": head}
    loaded, data, report = pilot.source_plan_snapshot(**options)
    assert loaded == profile and data == profile_data
    assert report["source_sha"] == head and len(report["source_tree"]) == 40
    assert report["plan_sha256"] == plan_sha and report["status"] == "source_verified"
    assert report["launch_authority"] is report["retry_authority"] is False
    assert report["supersedes_profile"] == pilot.SOURCE_PROFILE_PREVIOUS
    assert report["supersedes_profile_sha256"] == pilot.SOURCE_PROFILE_PREVIOUS_SHA256
    assert report["source_change_reason"] == "native_caps_enforcement_and_source_selector_refresh"
    assert report["run_id"] == original["pilot"]["run_id"]
    assert evidence._active_plan(plan_sha256=plan_sha, reviewed_source_sha=head)[0] == profile

    # The actual compiler selects this source, then preserves the frozen
    # grader's refusal. A new execution source cannot silently re-pin its judge.
    measured_hashes = []
    compute_hash = step8.compute_grader_source_hash

    def observed_hash(*args, **kwargs):
        value = compute_hash(*args, **kwargs)
        measured_hashes.append(value)
        return value

    monkeypatch.setattr(step8, "compute_grader_source_hash", observed_hash)
    with pytest.raises(identity.PilotIdentityRefused, match="^grader_template_source_drift$"):
        identity.compile_pilot_identity(profile, reviewed_source_sha=head)
    assert measured_hashes == ["0b5a59714e10b5193c88c32e934719741c8c17d4a433e565db38c21462802106"]
    assert profile["dispatch_grading_identity"]["grader_template_source_hash"] == (
        "47effd1db4c1de5ff7cf0473a034ece7748312e682597fb06ee480678e000fcf"
    )

    legacy, legacy_bytes, legacy_report = pilot.source_plan_snapshot()
    assert legacy == original and legacy_bytes == (root / pilot.ACTIVE_PLAN).read_bytes()
    assert legacy_report is None
    refused = pilot.inspect_plan(original)
    assert refused["configuration_valid"] is False
    assert set(refused["configuration_problems"]) == {
        "source_pin:" + name for name in pilot.SOURCE_PROFILE_REFRESH
    }
    assert refused["launch_allowed"] is refused["full_220_allowed"] is False

    for source in (None, "main", "0" * 40, "f3e0710a34b839b904aea2e2b1a16fded24546cf", CANARY):
        with pytest.raises(pilot.PilotSourceRegistrationRefused, match="^pilot_source_registration_refused$"):
            pilot.source_plan_snapshot(**{**options, "reviewed_source_sha": source})
    with pytest.raises(pilot.PilotSourceRegistrationRefused):
        pilot.source_plan_snapshot(**{**options, "expected_plan_sha256": "0" * 64})
    with pytest.raises(pilot.PilotSourceRegistrationRefused):
        pilot.source_plan_snapshot(**{**options, "expected_plan_sha256": pilot.seal(previous)})

    # Synthetic mutations do not alter any repository file or Git object.
    read_bytes = reader._read_bytes
    for missing in (False, True):
        def bad_predecessor(path, **kwargs):
            if path == previous_path:
                if missing:
                    raise FileNotFoundError(CANARY)
                return read_bytes(path, **kwargs) + b"\n"
            return read_bytes(path, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(reader, "_read_bytes", bad_predecessor)
            with pytest.raises(pilot.PilotSourceRegistrationRefused):
                pilot.source_plan_snapshot(**options)
    mutations = []
    changed = deepcopy(profile)
    changed["identity"]["model"] = "gpt-5.6-sol-fast"
    mutations.append(changed)
    changed = deepcopy(profile)
    changed["source_pins"][pilot.GRADER] = "0" * 64
    mutations.append(changed)
    changed = deepcopy(profile)
    changed["source_pins"]["batch-runner/gpt56_pilot_identity_plan.py"] = "0" * 64
    mutations.append(changed)
    changed = deepcopy(profile)
    del changed["source_pins"][pilot.GRADER]
    mutations.append(changed)
    for name in pilot.SOURCE_PROFILE_DELTA:
        changed = deepcopy(profile)
        changed["source_pins"][name] = previous["source_pins"][name]
        mutations.append(changed)
    for changed in mutations:
        encoded = yaml.safe_dump(changed).encode()
        with monkeypatch.context() as patch:
            patch.setattr(reader, "_read_bytes", lambda path, **kw: encoded if path == profile_path else read_bytes(path, **kw))
            with pytest.raises(pilot.PilotSourceRegistrationRefused):
                pilot.source_plan_snapshot(**{**options, "expected_plan_sha256": pilot.seal(changed)})

    with monkeypatch.context() as patch:
        patch.setattr(evidence, "__file__", str(tmp_path / CANARY))
        with pytest.raises(pilot.PilotSourceRegistrationRefused):
            pilot.source_plan_snapshot(**options)

    reads = []

    def final_drift(path, **kwargs):
        if path == root / "batch-runner/gpt56_pilot_identity_plan.py":
            reads.append(path)
            if len(reads) == 2:
                raise ValueError(CANARY)
        return read_bytes(path, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(reader, "_read_bytes", final_drift)
        with pytest.raises(pilot.PilotSourceRegistrationRefused, match="^pilot_source_registration_refused$"):
            pilot.source_plan_snapshot(**options)
    assert len(reads) == 2  # Admission read succeeded; the final reread refused.

    real_git = checkout._git
    for kind in ("foreign", "symlink", "wrong_commit"):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT,
                          pax_headers={"comment": "0" * 40 if kind == "wrong_commit" else head}) as archive:
            member = tarfile.TarInfo("unrelated.py" if kind == "foreign" else pilot.SOURCE_PROFILE)
            member.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.REGTYPE
            archive.addfile(member, io.BytesIO(b""))

        def wrong_archive(repository, *args, **kwargs):
            return SimpleNamespace(stdout=buffer.getvalue()) if args[0] == "archive" else real_git(repository, *args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(checkout, "_git", wrong_archive)
            with pytest.raises(pilot.PilotSourceRegistrationRefused):
                pilot.source_plan_snapshot(**options)

    assert pilot.main(["--plan", str(profile_path), "--reviewed-source-sha", head]) == 2
    completion = json.loads(capsys.readouterr().out)
    assert completion["source_registration"] == report
    assert completion["configuration_valid"] is True
    assert completion["launch_allowed"] is completion["full_220_allowed"] is False
    assert completion["launch_blockers"] == list(pilot.LAUNCH_BLOCKERS)
    assert completion["evidence_gate"]["evidence_complete"] is False
    assert pilot.main(["--plan", str(previous_path), "--reviewed-source-sha", head]) == 2
    previous_completion = json.loads(capsys.readouterr().out)
    assert previous_completion["source_registration"] == {
        "status": "refused", "refusal_code": "pilot_source_registration_refused",
    }
    assert previous_completion["launch_allowed"] is False
    with monkeypatch.context() as patch:
        patch.setattr(checkout, "_git", forbidden)
        assert pilot.main(["--plan", str(profile_path), "--reviewed-source-sha", head]) == 2
    output = capsys.readouterr()
    assert CANARY not in output.out + output.err
    assert json.loads(output.out)["source_registration"] == {
        "status": "refused", "refusal_code": "pilot_source_registration_refused",
    }
    assert forbidden_calls == [True]  # Only the deliberate safe-error injection.
    assert git_commands and set(git_commands) <= {"rev-parse", "status", "archive"}
