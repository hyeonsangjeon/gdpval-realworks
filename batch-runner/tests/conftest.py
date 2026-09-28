"""Immutable historical source bytes for explicitly requested legacy fixtures."""

import io
import os
from pathlib import Path
import subprocess
import tarfile

import pytest


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
