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
import gpt56_pilot_deployment_binding as binding
import gpt56_pilot_wire_receipt as wire
import gpt56_native_response_capture as native_response
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
    caps_path = root / pilot.SOURCE_PROFILE_CAPS
    caps_bytes = caps_path.read_bytes()
    caps_profile = pilot.load_plan(caps_path)
    bindings_path = root / pilot.SOURCE_PROFILE_BINDINGS
    bindings_bytes = bindings_path.read_bytes()
    bindings_profile = pilot.load_plan(bindings_path)
    token_path = root / pilot.SOURCE_PROFILE_TOKEN_PRECHECK
    token_bytes = token_path.read_bytes()
    token_profile = pilot.load_plan(token_path)
    usd_path = root / pilot.SOURCE_PROFILE_USD
    usd_bytes = usd_path.read_bytes()
    usd_profile = pilot.load_plan(usd_path)
    shared_path = root / pilot.SOURCE_PROFILE_SHARED
    shared_bytes = shared_path.read_bytes()
    shared_profile = pilot.load_plan(shared_path)
    usd200_path = root / pilot.SOURCE_PROFILE_USD200
    usd200_bytes = usd200_path.read_bytes()
    usd200_profile = pilot.load_plan(usd200_path)
    connection_path = root / pilot.SOURCE_PROFILE_CONNECTION
    connection_bytes = connection_path.read_bytes()
    connection_profile = pilot.load_plan(connection_path)
    response_path = root / pilot.SOURCE_PROFILE_RESPONSE
    response_bytes = response_path.read_bytes()
    response_profile = pilot.load_plan(response_path)
    runner_path = root / pilot.SOURCE_PROFILE_RUNNER
    runner_bytes = runner_path.read_bytes()
    runner_profile = pilot.load_plan(runner_path)
    paid_path = root / pilot.SOURCE_PROFILE_PAID_DIAGNOSTIC
    paid_bytes = paid_path.read_bytes()
    paid_profile = pilot.load_plan(paid_path)
    reference_path = root / binding.CONNECTION_REFERENCE_PATH
    assert pilot.SOURCE_PROFILE.endswith("_source_20261029_no_web_diagnostic.yaml")
    assert hashlib.sha256(paid_bytes).hexdigest() == pilot.SOURCE_PROFILE_PAID_DIAGNOSTIC_SHA256 == (
        "31c5448b105977e056530dc5df28a68c6480f1f7ccba8886e2f611fa04823b23"
    )
    assert hashlib.sha256(runner_bytes).hexdigest() == pilot.SOURCE_PROFILE_RUNNER_SHA256 == (
        "d01dcb4d47c3b913647a0ca56740532ed40f072976226a703e491ee3c510155d"
    )
    assert {name for name, digest in paid_profile["source_pins"].items()
            if digest != runner_profile["source_pins"][name]} == {
        "batch-runner/gpt56_sol_codex_pilot_preflight.py",
    }
    assert {name for name, digest in profile["source_pins"].items()
            if digest != paid_profile["source_pins"][name]} == {
        "batch-runner/core/codex_runner.py", "batch-runner/gpt56_sol_codex_pilot_preflight.py",
    }
    assert {k: v for k, v in profile.items() if k != "source_pins"} == {
        k: v for k, v in paid_profile.items() if k != "source_pins"
    }
    assert {k: v for k, v in profile.items() if k != "source_pins"} == {
        k: v for k, v in runner_profile.items() if k != "source_pins"
    }
    assert hashlib.sha256(response_bytes).hexdigest() == pilot.SOURCE_PROFILE_RESPONSE_SHA256 == (
        "768adaed42d65233986447810dd5a8646306b3e44f42bf7feb2037042b9c1446"
    )
    assert hashlib.sha256(connection_bytes).hexdigest() == pilot.SOURCE_PROFILE_CONNECTION_SHA256 == (
        "84b74f81bddb623d6b0cc34e0cff4b90696f8016890e119de8febaa4990092aa"
    )
    assert {name for name, digest in response_profile["source_pins"].items()
            if digest != connection_profile["source_pins"][name]} == {
        "batch-runner/core/codex_runner.py", "batch-runner/gpt56_pilot_wire_receipt.py",
        "batch-runner/gpt56_sol_codex_pilot_preflight.py",
    }
    assert {name for name, digest in profile["source_pins"].items()
            if digest != response_profile["source_pins"][name]} == {
        "batch-runner/core/codex_runner.py", "batch-runner/step2_run_inference.py",
        "batch-runner/gpt56_pilot_wire_receipt.py", "batch-runner/gpt56_pilot_native_result_host.py",
        "batch-runner/gpt56_sol_codex_pilot_preflight.py", "batch-runner/step8_grade.py",
        "batch-runner/core/grader.py", "batch-runner/core/grade_payload.py",
    }
    assert {k: v for k, v in profile.items() if k != "source_pins"} == {
        k: v for k, v in response_profile.items() if k != "source_pins"
    }
    assert {k: v for k, v in profile.items() if k != "source_pins"} == {
        k: v for k, v in connection_profile.items() if k != "source_pins"
    }
    assert hashlib.sha256(usd200_bytes).hexdigest() == pilot.SOURCE_PROFILE_USD200_SHA256 == (
        "d05363c8745245c8279fb9b30404e88922b79b26e874ed3d97a2c0444de9715d"
    )
    assert {name for name, digest in connection_profile["source_pins"].items()
            if digest != usd200_profile["source_pins"][name]} == {
        "batch-runner/gpt56_sol_codex_pilot_preflight.py", "batch-runner/gpt56_pilot_wire_receipt.py",
        "batch-runner/gpt56_pilot_deployment_binding.py",
    }
    assert {name for name, digest in usd200_profile["source_pins"].items()
            if digest != shared_profile["source_pins"][name]} == {
        "batch-runner/gpt56_sol_codex_pilot_preflight.py", "batch-runner/gpt56_pilot_wire_receipt.py",
    }
    assert {k: v for k, v in profile.items() if k != "source_pins"} == {
        k: v for k, v in usd200_profile.items() if k != "source_pins"
    }
    assert hashlib.sha256(shared_bytes).hexdigest() == pilot.SOURCE_PROFILE_SHARED_SHA256 == (
        "7619cd0c6baa35a8660c2e076ed171f271f6b4ad3c5de7115b19e7f2f30a7652"
    )
    assert {name for name, digest in connection_profile["source_pins"].items()
            if digest != shared_profile["source_pins"][name]} == {
        "batch-runner/gpt56_sol_codex_pilot_preflight.py", "batch-runner/gpt56_pilot_wire_receipt.py",
        "batch-runner/gpt56_pilot_deployment_binding.py",
    }
    assert {k: v for k, v in profile.items() if k != "source_pins"} == {
        k: v for k, v in shared_profile.items() if k != "source_pins"
    }
    assert hashlib.sha256(usd_bytes).hexdigest() == pilot.SOURCE_PROFILE_USD_SHA256 == (
        "d2398e54ddad22bc42e6d47bce12ef3b3053f575f2ac5725e605dc3a516e3f29"
    )
    assert hashlib.sha256(token_bytes).hexdigest() == pilot.SOURCE_PROFILE_TOKEN_PRECHECK_SHA256 == (
        "fbabe0aa40f6513bc77d86a29ae9ac9af35cfbd64b5b70fe3f6150aa0a6e1a44"
    )
    assert pilot.SOURCE_PROFILE_BINDINGS.endswith("_source_20261025_bindings.yaml")
    assert hashlib.sha256(bindings_bytes).hexdigest() == pilot.SOURCE_PROFILE_BINDINGS_SHA256 == (
        "740ec085c047ad359b4c5e56a8bf5867ebc2cb6c229d479262d6815fbe8154cf"
    )
    assert pilot.SOURCE_PROFILE_CAPS.endswith("_source_20261025.yaml")
    assert pilot.SOURCE_PROFILE_PREVIOUS.endswith("_source_20261023.yaml")
    assert hashlib.sha256(caps_bytes).hexdigest() == pilot.SOURCE_PROFILE_CAPS_SHA256 == (
        "f88c850558674a4c3a89ae0840f23dc27402aefafe56f7323ba3d3b8ad33a3b2"
    )
    assert {name for name, digest in bindings_profile["source_pins"].items()
            if digest != caps_profile["source_pins"][name]} == {"batch-runner/gpt56_sol_codex_pilot_preflight.py"}
    assert {name for name, digest in connection_profile["source_pins"].items()
            if digest != bindings_profile["source_pins"][name]} == {
        "batch-runner/gpt56_sol_codex_pilot_preflight.py", "batch-runner/gpt56_pilot_wire_receipt.py",
        "batch-runner/step8_grade.py", "batch-runner/gpt56_pilot_deployment_binding.py",
    }
    assert {name for name, digest in connection_profile["source_pins"].items()
            if digest != token_profile["source_pins"][name]} == {
        "batch-runner/gpt56_sol_codex_pilot_preflight.py", "batch-runner/gpt56_pilot_wire_receipt.py",
        "batch-runner/step8_grade.py", "batch-runner/gpt56_pilot_deployment_binding.py",
    }
    assert {name for name, digest in connection_profile["source_pins"].items()
            if digest != usd_profile["source_pins"][name]} == {
        "batch-runner/gpt56_sol_codex_pilot_preflight.py", "batch-runner/gpt56_pilot_wire_receipt.py",
        "batch-runner/step8_grade.py", "batch-runner/gpt56_pilot_deployment_binding.py",
    }
    assert {k: v for k, v in profile.items() if k != "source_pins"} == {
        k: v for k, v in usd_profile.items() if k != "source_pins"
    }
    assert {name for name, digest in usd_profile["source_pins"].items()
            if digest != token_profile["source_pins"][name]} == {
        "batch-runner/gpt56_sol_codex_pilot_preflight.py", "batch-runner/gpt56_pilot_wire_receipt.py",
    }
    assert {k: v for k, v in profile.items() if k != "source_pins"} == {
        k: v for k, v in token_profile.items() if k != "source_pins"
    }
    assert {k: v for k, v in profile.items() if k != "source_pins"} == {
        k: v for k, v in bindings_profile.items() if k != "source_pins"
    }
    assert {k: v for k, v in profile.items() if k != "source_pins"} == {
        k: v for k, v in caps_profile.items() if k != "source_pins"
    }
    assert hashlib.sha256(previous_bytes).hexdigest() == (
        pilot.SOURCE_PROFILE_PREVIOUS_SHA256
    ) == "506de35370ffe6d54e6decb2459a4f4abda47136d550c010086b0fffd5c1e482"
    assert {name for name, digest in profile["source_pins"].items()
            if digest != previous["source_pins"][name]} == pilot.SOURCE_PROFILE_DELTA == {
        "batch-runner/core/codex_runner.py", "batch-runner/step2_run_inference.py",
        "batch-runner/gpt56_pilot_wire_receipt.py", "batch-runner/gpt56_pilot_runtime_caps_usage.py",
        "batch-runner/gpt56_sol_codex_pilot_preflight.py",
        "batch-runner/step8_grade.py", "batch-runner/gpt56_pilot_deployment_binding.py",
        "batch-runner/gpt56_pilot_native_result_host.py",
        "batch-runner/core/grader.py", "batch-runner/core/grade_payload.py",
    }
    assert {k: v for k, v in profile.items() if k != "source_pins"} == {
        k: v for k, v in previous.items() if k != "source_pins"
    }
    shared = root / "batch-runner/gpt54_disposable_checkout.py"
    assert hashlib.sha256(shared.read_bytes()).hexdigest() == next(iter(pilot.SOURCE_PROFILE_AUXILIARY.values()))
    assert pilot.SOURCE_PROFILE_AUXILIARY == {
        "batch-runner/gpt54_disposable_checkout.py": "77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62",
        pilot.ENVELOPE + "gpt56_sol_native_usd_cap_20261027.yaml": wire.USD_CAPS_SHA256,
        pilot.ENVELOPE + "model_price_table.json": wire.USD_PRICE_TABLE_SHA256,
        "batch-runner/gpt56_pilot_usd_budget.py": "d28dbe71db00d301e2dad54852515df15c254be09002fa43b16e2d0f2131048e",
        "batch-runner/core/cost_metering.py": "f2d63e7812bd8557232bc0a3bdc0deb76a3565a4d1398b1fb191008fa9aff888",
        binding.CONNECTION_REFERENCE_PATH: binding.CONNECTION_REFERENCE_SHA256,
        "batch-runner/gpt56_native_response_capture.py": "1e3db1b4f6b956b24fd6b892118e0d4a2b491c23e3a52c8a1536849a6a36aca6",
        "batch-runner/scripts/diagnose_codex_foundry_connection.py": "ca4b9cd3adaffa48b1c37e2384f667b46779e8621752c33291017c4939d26d3f",
        ".github/workflows/codex-foundry-connection-diagnostic.yml": "2b8f15dfe68ed0259ee2058f4c36fb6a5a051dec86bbb8b26a713602a5e0aa6b",
        "batch-runner/core/runner_environment.py": "c63dab5c607e565f82429c310d8aa5f032390ad1160b62512182ee8586d0511a",
        "batch-runner/scripts/prepare_codex_sandbox_host.py": "6324b206656abf609af6c6d4f8a1c93c68a0c3d48e53aef0d35955630b66825a",
        "batch-runner/step9_merge_shards.py": "9079fd701fbc7e4cca65fbcc1705f03891e4e13be3a4fb9145a2bb17b1352872",
        ".github/workflows/batch-run.yml": "06519bc2abb0f69fe688cd864dadb536e907a433e2726c5bf60c1115c5c220bb",
    }
    for role, digest in pilot.SOURCE_PROFILE_AUXILIARY.items():
        assert hashlib.sha256((root / role).read_bytes()).hexdigest() == digest
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
    assert report["supersedes_profile"] == pilot.SOURCE_PROFILE_PAID_DIAGNOSTIC
    assert report["supersedes_profile_sha256"] == pilot.SOURCE_PROFILE_PAID_DIAGNOSTIC_SHA256
    assert report["source_change_reason"] == "connected_diagnostic_native_web_search_disabled_unchanged_token_precheck"
    assert report["response_capture_readiness"] == {
        "status": "next_call_capture_path_only", "live_evidence_observed": False,
        "eligible_blockers": ["foundry_served_model_version_unverified", "max_and_long_1m_capability_unverified"],
        "cleared_blockers": [], "missing_response_field": "not_reported",
        "provider_emits_required_fields_verified": False,
    }
    assert report["monetary_decision"] == {
        "record": pilot.ENVELOPE + "gpt56_sol_native_usd_cap_20261027.yaml",
        "sha256": wire.USD_CAPS_SHA256, "approved_maximum_usd": 200, "currency": "USD",
        "approved_at_utc": "2026-10-27T01:56:00Z",
        "approved_at_local": "2026-10-27T10:56:00+09:00", "approval_source": "owner_card_record",
        "scope": "five_task_pilot_inference_and_grading_combined",
        "actual_billing_hard_limit_verified": False, "grading_ledger_connected": True,
        "grading_price_contract_verified": False,
    }
    assert report["run_id"] == original["pilot"]["run_id"]
    assert evidence._active_plan(plan_sha256=plan_sha, reviewed_source_sha=head)[0] == profile

    # The source-held historical target closes exactly one requirement. No
    # evidence/compiler/provider seam is replaced by a synthetic success.
    connection_options = {"retained_connection": reference_path,
                          "retained_connection_source_sha": head}
    connected = pilot.inspect_plan(profile, **connection_options)
    remaining = [name for name in pilot.LAUNCH_BLOCKERS if name != binding.CONNECTION_BLOCKER]
    assert connected["configuration_valid"] is True
    assert connected["launch_allowed"] is connected["full_220_allowed"] is False
    assert connected["launch_blockers"] == remaining and len(remaining) == 10
    connection_gate = connected["approved_connection_gate"]
    assert connection_gate["configured_route_bound"] is True
    assert connection_gate["cleared_blockers"] == [binding.CONNECTION_BLOCKER]
    assert connection_gate["served_model_verified"] is connection_gate["reasoning_max_verified"] is False
    assert connection_gate["long_1m_verified"] is False
    assert connection_gate["historical_observation"]["served_model"] is None
    assert connection_gate["historical_observation"]["model_context_window"] == 258400
    for bad_options in (
        {"retained_connection": tmp_path / CANARY},
        {"retained_connection_source_sha": None},
        {"retained_connection_source_sha": "0" * 40},
        {"reviewed_source_sha": head, "evidence_bundle": tmp_path / CANARY, "as_of": "2026-10-27T00:00:00Z"},
    ):
        refused_connection = pilot.inspect_plan(profile, **{**connection_options, **bad_options})
        assert refused_connection["launch_blockers"] == list(pilot.LAUNCH_BLOCKERS)
        assert refused_connection["approved_connection_gate"]["cleared_blockers"] == []
        assert refused_connection["approved_connection_gate"]["refusal_code"] == "approved_connection_reference_refused"
        assert CANARY not in json.dumps(refused_connection)
    with monkeypatch.context() as patch:
        def missing_reference():
            raise binding.PilotDeploymentBindingRefused(CANARY)
        patch.setattr(binding, "approved_connection_reference", missing_reference)
        refused_connection = pilot.inspect_plan(profile, **connection_options)
        assert refused_connection["launch_blockers"] == list(pilot.LAUNCH_BLOCKERS)
        assert CANARY not in json.dumps(refused_connection)

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
    # The existing closure includes every core/*.py, including this change's
    # runner adapter. Update only the observed current hash, never the frozen
    # grader pin or its mandatory source-drift refusal.
    assert measured_hashes == ["099755b009e7563e5b3824ac34c1ab2cf5c83b3cdf4aba7886b50e1c28003fd7"]
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
    with pytest.raises(pilot.PilotSourceRegistrationRefused):
        pilot.source_plan_snapshot(**{**options, "expected_plan_sha256": pilot.seal(caps_profile)})
    with pytest.raises(pilot.PilotSourceRegistrationRefused):
        pilot.source_plan_snapshot(**{**options, "expected_plan_sha256": pilot.seal(token_profile)})
    with pytest.raises(pilot.PilotSourceRegistrationRefused):
        pilot.source_plan_snapshot(**{**options, "expected_plan_sha256": pilot.seal(shared_profile)})
    with pytest.raises(pilot.PilotSourceRegistrationRefused):
        pilot.source_plan_snapshot(**{**options, "expected_plan_sha256": pilot.seal(usd200_profile)})
    with pytest.raises(pilot.PilotSourceRegistrationRefused):
        pilot.source_plan_snapshot(**{**options, "expected_plan_sha256": pilot.seal(connection_profile)})

    # Synthetic mutations do not alter any repository file or Git object.
    read_bytes = reader._read_bytes
    for predecessor_path in (previous_path, caps_path, token_path, shared_path, usd200_path, connection_path,
                             root / "batch-runner/gpt56_native_response_capture.py",
                             wire._USD_CAPS_PATH, wire._USD_PRICE_PATH, reference_path):
        for missing in (False, True):
            def bad_predecessor(path, **kwargs):
                if path == predecessor_path:
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
    changed = deepcopy(profile)
    # A changed allowed role still cannot bypass its held reviewed bytes.
    changed["source_pins"]["batch-runner/gpt56_pilot_wire_receipt.py"] = "1" * 64
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

    for module in (evidence, binding, native_response):
        with monkeypatch.context() as patch:
            patch.setattr(module, "__file__", str(tmp_path / CANARY))
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

    caps_reads = []

    def final_caps_drift(path, **kwargs):
        if path == caps_path:
            caps_reads.append(path)
            if len(caps_reads) == 3:
                raise ValueError(CANARY)
        return read_bytes(path, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(reader, "_read_bytes", final_caps_drift)
        with pytest.raises(pilot.PilotSourceRegistrationRefused, match="^pilot_source_registration_refused$"):
            pilot.source_plan_snapshot(**options)
    assert len(caps_reads) == 3  # Initial selection, admission, final reread.

    bindings_reads = []

    def final_bindings_drift(path, **kwargs):
        if path == bindings_path:
            bindings_reads.append(path)
            if len(bindings_reads) == 3:
                raise ValueError(CANARY)
        return read_bytes(path, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(reader, "_read_bytes", final_bindings_drift)
        with pytest.raises(pilot.PilotSourceRegistrationRefused, match="^pilot_source_registration_refused$"):
            pilot.source_plan_snapshot(**options)
    assert len(bindings_reads) == 3

    for held_role in (pilot.SOURCE_PROFILE_TOKEN_PRECHECK, pilot.SOURCE_PROFILE_USD, pilot.SOURCE_PROFILE_SHARED,
                      pilot.SOURCE_PROFILE_USD200, pilot.SOURCE_PROFILE_CONNECTION, binding.CONNECTION_REFERENCE_PATH,
                      "batch-runner/gpt56_native_response_capture.py",
                      "batch-runner/scripts/diagnose_codex_foundry_connection.py",
                      ".github/workflows/codex-foundry-connection-diagnostic.yml",
                      pilot.ENVELOPE + "gpt56_sol_native_usd_cap_20261027.yaml",
                      pilot.ENVELOPE + "model_price_table.json", "batch-runner/gpt56_pilot_usd_budget.py",
                      "batch-runner/core/cost_metering.py"):
        checks = []
        expected_reads = 3 if held_role in {pilot.SOURCE_PROFILE_TOKEN_PRECHECK, pilot.SOURCE_PROFILE_USD,
                                          pilot.SOURCE_PROFILE_SHARED, pilot.SOURCE_PROFILE_USD200,
                                          pilot.SOURCE_PROFILE_CONNECTION} else 2
        def final_money_drift(path, **kwargs):
            if path == root / held_role:
                checks.append(path)
                if len(checks) == expected_reads:
                    raise ValueError(CANARY)
            return read_bytes(path, **kwargs)
        with monkeypatch.context() as patch:
            patch.setattr(reader, "_read_bytes", final_money_drift)
            with pytest.raises(pilot.PilotSourceRegistrationRefused, match="^pilot_source_registration_refused$"):
                pilot.source_plan_snapshot(**options)
        assert len(checks) == expected_reads  # Both admission and final held-blob checks.

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
    assert pilot.main(["--plan", str(profile_path), "--reviewed-source-sha", head,
                       "--retained-connection-reference", str(reference_path)]) == 2
    bound_completion = json.loads(capsys.readouterr().out)
    assert bound_completion["source_registration"] == report
    assert bound_completion["launch_blockers"] == remaining
    assert bound_completion["approved_connection_gate"] == connection_gate
    assert bound_completion["launch_allowed"] is bound_completion["full_220_allowed"] is False
    for predecessor_path in (previous_path, caps_path, bindings_path):
        assert pilot.main(["--plan", str(predecessor_path), "--reviewed-source-sha", head]) == 2
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
