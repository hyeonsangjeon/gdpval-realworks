"""Pin hosted Ubuntu without changing workflow behavior or historical seals."""

import hashlib
from pathlib import Path
import re

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
# Before/after bytes at main 7c1f4c94067485be3170612258639d739d07d585.
# Every historical value remains checked; only these job runner lines differ.
RUNNER_PINS = {
    "agentic-v2-stage-a-probe.yml": (
        "59e5789b36ad130fea25e5d83db10497f5a91ba0d50de7ecef464fdcf275992d",
        "68d31832a47d126215d07705e24afb32ccf3ab1902ecd199fac5d32dfdfff1b4",
        ("free", "paid"),
    ),
    "agentic-v2-stage-run.yml": (
        "f02579edfa09ee9d3e9576cff25510c27f86bb1a9498f311f0bafd9ff4261ae1",
        "4ef1cea1b561d686480a9b2dadc737655bcd3a68e5ed1f39b9e70aaff22dafd2",
        ("free", "paid", "collect", "comparison-admission"),
    ),
    "backend-tests.yml": (
        "75e6db775426a8470d2757f2ae62fafc2a806f0f2684ed59925480956ad3ac65",
        "9ec98746110499a2f199e1322a8568effcd7c8b174e04b35661420e64a06af51",
        ("pytest", "comparison-contracts", "pilot-contracts", "budget-readout-contracts",
         "pilot-preflight-contracts", "pilot-external-receipt-contracts",
         "pilot-external-publication-contracts", "wire-contracts", "native-host-contracts"),
    ),
    "batch-run.yml": (
        "06519bc2abb0f69fe688cd864dadb536e907a433e2726c5bf60c1115c5c220bb",
        "a7b65f7d8f167cc0b13c940b90b84334dcfed876608696baedccf0a7b414a9cd",
        ("inspect-mode", "reject-agentic", "reject-unconfirmed-codex", "batch-run", "comparison-admission"),
    ),
    "build-sandbox-image.yml": (
        "8c79b85f0c692d3a5c5897bd8f2eafb82af44412687b31982cb00d4c5e6ab043",
        "234c1b269b582425f7b4f344f6dffb8a89f5ad0503afae256f359726597e9d16",
        ("build-sandbox-image", "hosted-containment-measurement"),
    ),
    "execution-envelope-preflight.yml": (
        "62cc8887244fe1cc7a7643c512a65b3b23f95d4f429bd1e2f15d9117b6672c49",
        "25cd47ce3b63bc38d0eea51f6c4e4c5eb519a7fe4c21557ec318086841d68dd7",
        ("advance-check",),
    ),
    "grader-hash-freeze.yml": (
        "306e59b7e97fabcfc78a4bee75f41ad0bd1342a3a4b727caf06d6c8dcd85ea0f",
        "2161be71ce5c24f5c0afcd09efcf1c1e3964d844c3ad916d5f6e420fb1e1ac7c",
        ("freeze-check",),
    ),
}
PREVIOUS_BATCH_RUNNER = (
    "${{ needs.inspect-mode.outputs.uses_codex_foundry == 'true' "
    "&& 'ubuntu-24.04' || 'ubuntu-latest' }}"
)


def restore_pre_ubuntu_2404_runner_bytes(name, data):
    """Undo exactly the approved runner lines, requiring both complete hashes."""
    historical_hash, current_hash, changed_jobs = RUNNER_PINS[name]
    assert hashlib.sha256(data).hexdigest() == current_hash
    jobs = yaml.safe_load(data)["jobs"]
    assert all(jobs[job]["runs-on"] == "ubuntu-24.04" for job in changed_jobs)
    lines = data.decode("utf-8").splitlines(keepends=True)
    current_job = None
    restored = set()
    for index, line in enumerate(lines):
        match = re.fullmatch(r"  ([A-Za-z0-9_-]+):\n", line)
        if match:
            current_job = match[1]
        if current_job in changed_jobs and line.startswith("    runs-on:"):
            assert current_job not in restored
            assert line == "    runs-on: ubuntu-24.04\n"
            previous = (PREVIOUS_BATCH_RUNNER if name == "batch-run.yml" and current_job == "batch-run"
                        else "ubuntu-latest")
            lines[index] = f"    runs-on: {previous}\n"
            restored.add(current_job)
    assert restored == set(changed_jobs)
    historical = "".join(lines).encode("utf-8")
    assert hashlib.sha256(historical).hexdigest() == historical_hash
    return historical


@pytest.mark.parametrize("name", RUNNER_PINS)
def test_only_reviewed_runner_lines_change_and_historical_bytes_survive(name):
    historical = restore_pre_ubuntu_2404_runner_bytes(name, (WORKFLOWS / name).read_bytes())
    before = yaml.safe_load(historical)
    after = yaml.safe_load((WORKFLOWS / name).read_bytes())
    for job in RUNNER_PINS[name][2]:
        before["jobs"][job]["runs-on"] = "ubuntu-24.04"
    assert before == after


@pytest.mark.parametrize("name", RUNNER_PINS)
@pytest.mark.parametrize("mutation", ["floating", "other_release", "extra_byte", "old_bytes"])
def test_runner_reconstruction_rejects_unreviewed_bytes(name, mutation):
    data = (WORKFLOWS / name).read_bytes()
    if mutation == "floating":
        data = data.replace(b"    runs-on: ubuntu-24.04\n", b"    runs-on: ubuntu-latest\n", 1)
    elif mutation == "other_release":
        data = data.replace(b"    runs-on: ubuntu-24.04\n", b"    runs-on: ubuntu-26.04\n", 1)
    elif mutation == "extra_byte":
        data += b"\n"
    else:
        data = restore_pre_ubuntu_2404_runner_bytes(name, data)
    with pytest.raises(AssertionError):
        restore_pre_ubuntu_2404_runner_bytes(name, data)


def _assert_versioned_hosted_runner(name, job_name, job):
    runner = job.get("runs-on")
    if "uses" in job:
        assert runner is None  # Reusable workflows choose their own runner.
    elif isinstance(runner, list):
        assert (name, job_name) == ("agentic-sandbox-preflight.yml", "model-free-preflight")
        assert runner == ["self-hosted", "linux", "x64", "agentic-sandbox"]
    elif runner == "${{ matrix.runner }}":
        assert (name, job_name) == ("codex-sandbox-host-survey.yml", "survey")
        matrix = job["strategy"]["matrix"]
        assert set(matrix) == {"include"}
        assert {entry["runner"] for entry in matrix["include"]} == {"ubuntu-22.04", "ubuntu-24.04"}
    else:
        assert isinstance(runner, str) and re.fullmatch(r"ubuntu-\d{2}\.\d{2}", runner)


def test_all_hosted_ubuntu_runners_are_versioned_including_matrix_entries():
    paths = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    assert paths and sum(len(entry[2]) for entry in RUNNER_PINS.values()) == 24
    for path in paths:
        for job_name, job in yaml.safe_load(path.read_bytes())["jobs"].items():
            _assert_versioned_hosted_runner(path.name, job_name, job)


@pytest.mark.parametrize("runner", ["ubuntu", "ubuntu-latest", "linux", "${{ matrix.unknown }}"])
def test_floating_or_unresolved_hosted_runners_are_refused(runner):
    with pytest.raises(AssertionError):
        _assert_versioned_hosted_runner("new.yml", "new", {"runs-on": runner})


def test_python_pin_and_time_budget_control_runner_are_unchanged():
    jobs = yaml.safe_load((WORKFLOWS / "backend-tests.yml").read_bytes())["jobs"]
    assert jobs["time-budget-contracts"]["runs-on"] == "ubuntu-22.04"
    for job in jobs.values():
        setup = [step for step in job["steps"] if step.get("name") == "Setup Python"]
        assert len(setup) == 1 and setup[0]["with"]["python-version"] == "3.10.12"
    preflight = yaml.safe_load((WORKFLOWS / "execution-envelope-preflight.yml").read_bytes())
    setup = [step for step in preflight["jobs"]["advance-check"]["steps"]
             if step.get("name") == "Setup Python"]
    assert len(setup) == 1 and setup[0]["with"]["python-version"] == "3.10.12"
