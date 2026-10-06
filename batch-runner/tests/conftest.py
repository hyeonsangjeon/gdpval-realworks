"""Immutable historical source bytes for explicitly requested legacy fixtures."""

import io
import os
from pathlib import Path
import subprocess
import tarfile

import pytest


@pytest.fixture(scope="session")
def frozen_local_comparison_source(tmp_path_factory):
    """F882 supplies historical positive bytes, never the current runtime R."""
    frozen_sha = "882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2"
    archived = subprocess.run(
        ["git", "archive", "--format=tar", frozen_sha, "batch-runner", ".github/workflows"],
        cwd=Path(__file__).resolve().parents[2], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        env={"PATH": os.defpath, "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1",
             "GIT_CONFIG_GLOBAL": os.devnull, "GIT_NO_LAZY_FETCH": "1"},
    ).stdout
    root = tmp_path_factory.mktemp("frozen-local-comparison-source")
    with tarfile.open(fileobj=io.BytesIO(archived), mode="r:") as snapshot:
        assert snapshot.pax_headers["comment"] == frozen_sha
        assert all(not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
                   and (member.isdir() or member.isfile()) for member in snapshot.getmembers())
        snapshot.extractall(root)
    return root


@pytest.fixture
def historical_retention_source(frozen_local_comparison_source, monkeypatch):
    """The closed eight-cell compiler refuses R and validates its real F bytes.

    This test-only fixture changes a source root, never hashes, verdicts, paid
    bindings or the current observer's dependencies. Synthetic retained-cell
    helpers explicitly copy this frozen core when exercising old positive paths.
    """
    import codex_retention_diagnostic as registration

    current = registration.ROOT
    with pytest.raises(registration.RetentionRegistrationRefused,
                       match="^source_pin:batch-runner/core/codex_runner.py$"):
        registration.compile_plan()
    frozen = frozen_local_comparison_source
    assert (frozen / registration.REGISTRATION).read_bytes() == (current / registration.REGISTRATION).read_bytes()
    assert (frozen / registration.COMPILER).read_bytes() == (current / registration.COMPILER).read_bytes()
    monkeypatch.setattr(registration, "ROOT", frozen)
    return frozen


@pytest.fixture(scope="module")
def approved_pilot_source(tmp_path_factory):
    """Read immutable local Git data before the function-scoped process guard.

    Only fixture materialization uses Git. Compilation runs with the requesting
    test's existing process, network and credential guards installed.
    """
    approved_sha = "8ac891e3e0e4752fe15a00139a2691ddf9df7dce"
    archived = subprocess.run(
        ["git", "archive", "--format=tar", approved_sha, "batch-runner", ".github/workflows"],
        cwd=Path(__file__).resolve().parents[2], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        env={"PATH": os.defpath, "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1",
             "GIT_CONFIG_GLOBAL": os.devnull, "GIT_NO_LAZY_FETCH": "1"},
    ).stdout
    source = tmp_path_factory.mktemp("native-approved-source")
    with tarfile.open(fileobj=io.BytesIO(archived), mode="r:") as snapshot:
        assert snapshot.pax_headers["comment"] == approved_sha
        assert all(
            not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
            and (member.isdir() or member.isfile()) for member in snapshot.getmembers()
        )
        snapshot.extractall(source)
    return source


@pytest.fixture
def historical_comparison_source(approved_pilot_source, monkeypatch):
    """Keep current-source refusal separate from explicitly requested legacy cases."""
    import gpt54_comparison_preflight as comparison

    current = comparison.inspect_plan(comparison.load_plan())
    assert current["configuration_valid"] is False
    assert current["configuration_problems"] == [
        "source_pin:batch-runner/gpt54_prepared_input_attestation.py",
        "source_pin:batch-runner/gpt54_codex_input_capture.py",
        "source_pin:batch-runner/gpt54_v2_input_capture.py",
        "source_pin:batch-runner/gpt54_run_config_bundle.py",
        "source_pin:batch-runner/gpt54_run_input_bundle.py",
        "source_pin:batch-runner/gpt54_disposable_checkout.py",
        "source_pin:batch-runner/gpt54_workflow_gate.py",
        "source_pin:batch-runner/core/agentic_v2_conversation_runner.py",
        "source_pin:batch-runner/core/codex_runner.py",
        "source_pin:batch-runner/step2_run_inference.py",
        "source_pin:batch-runner/core/codex_task_deadline.py",
    ]
    plan = approved_pilot_source / comparison.PLAN.relative_to(comparison.ROOT)
    assert plan.read_bytes() == comparison.PLAN.read_bytes()
    monkeypatch.setattr(comparison, "ROOT", approved_pilot_source)
    monkeypatch.setattr(comparison, "PLAN", plan)
    return approved_pilot_source


@pytest.fixture(scope="module")
def historical_foundry_source(approved_pilot_source):
    """Keep one explicit source context discoverable by imported seed consumers."""
    import gpt56_sol_codex_pilot_preflight as pilot

    plan = approved_pilot_source / pilot.PLAN.relative_to(pilot.ROOT)
    assert plan.read_bytes() == pilot.PLAN.read_bytes()
    with pytest.MonkeyPatch.context() as source:
        source.setattr(pilot, "ROOT", approved_pilot_source)
        source.setattr(pilot, "PLAN", plan)
        yield approved_pilot_source


@pytest.fixture(scope="module")
def historical_budget_source(approved_pilot_source):
    """Bind legacy compilers before shared histories, never via an autouse override."""
    import codex_budget_pilot as pilot
    import codex_budget_pilot_ci as ci
    import gpt54_comparison_preflight as comparison

    current = comparison.inspect_plan(comparison.load_plan())
    assert current["configuration_valid"] is False
    assert current["configuration_problems"] == [
        "source_pin:batch-runner/gpt54_prepared_input_attestation.py",
        "source_pin:batch-runner/gpt54_codex_input_capture.py",
        "source_pin:batch-runner/gpt54_v2_input_capture.py",
        "source_pin:batch-runner/gpt54_run_config_bundle.py",
        "source_pin:batch-runner/gpt54_run_input_bundle.py",
        "source_pin:batch-runner/gpt54_disposable_checkout.py",
        "source_pin:batch-runner/gpt54_workflow_gate.py",
        "source_pin:batch-runner/core/agentic_v2_conversation_runner.py",
        "source_pin:batch-runner/core/codex_runner.py",
        "source_pin:batch-runner/step2_run_inference.py",
        "source_pin:batch-runner/core/codex_task_deadline.py",
    ]
    # Derive each path while ROOT still names its owning tree.
    plan = approved_pilot_source / comparison.PLAN.relative_to(comparison.ROOT)
    registration = approved_pilot_source / pilot.REGISTRATION.relative_to(pilot.ROOT)
    ci_registration = approved_pilot_source / ci.REGISTRATION.relative_to(pilot.ROOT)
    assert plan.read_bytes() == comparison.PLAN.read_bytes()
    assert registration.read_bytes() == pilot.REGISTRATION.read_bytes()
    assert ci_registration.read_bytes() == ci.REGISTRATION.read_bytes()
    with pytest.MonkeyPatch.context() as source:
        source.setattr(comparison, "ROOT", approved_pilot_source)
        source.setattr(comparison, "PLAN", plan)
        source.setattr(pilot, "ROOT", approved_pilot_source)
        source.setattr(pilot, "REGISTRATION", registration)
        source.setattr(ci, "REGISTRATION", ci_registration)
        yield approved_pilot_source
