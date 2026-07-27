"""Static fail-closed checks for agentic GitHub workflows."""

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
BATCH_WORKFLOW = ROOT / ".github" / "workflows" / "batch-run.yml"
BUILD_WORKFLOW = ROOT / ".github" / "workflows" / "build-sandbox-image.yml"
PREFLIGHT_WORKFLOW = (
    ROOT / ".github" / "workflows" / "agentic-sandbox-preflight.yml"
)


def _steps(path):
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return next(iter(document["jobs"].values()))["steps"]


def _assert_actions_are_commit_pinned(path):
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    references = [
        str(step["uses"])
        for job in document["jobs"].values()
        for step in job.get("steps", [])
        if "uses" in step
    ]
    assert references
    assert all(
        re.search(r"@[0-9a-f]{40}$", reference) is not None
        for reference in references
    )


def test_general_batch_blocks_agentic_before_any_credential_step():
    _assert_actions_are_commit_pinned(BATCH_WORKFLOW)
    document = yaml.safe_load(BATCH_WORKFLOW.read_text(encoding="utf-8"))
    inspect_job = document["jobs"]["inspect-mode"]
    reject_job = document["jobs"]["reject-agentic"]
    batch_job = document["jobs"]["batch-run"]
    steps = batch_job["steps"]
    names = [step.get("name", "") for step in steps]
    block_index = names.index("Block agentic modes in credentialed general workflow")

    assert inspect_job["permissions"] == {"contents": "read"}
    assert inspect_job["outputs"]["uses_agentic"] == (
        "${{ steps.mode.outputs.uses_agentic }}"
    )
    inspect_checkout = next(
        step for step in inspect_job["steps"] if step.get("name") == "Checkout config only"
    )
    assert inspect_checkout["with"]["persist-credentials"] is False
    assert "YAML.safe_load" in inspect_job["steps"][-1]["run"]
    inspect_script = inspect_job["steps"][-1]["run"]
    assert "'agentic_sandbox'" in inspect_script
    assert "'agentic_sandbox_v2'" in inspect_script
    assert reject_job["if"] == (
        "needs.inspect-mode.outputs.uses_agentic == 'true'"
    )
    assert batch_job["needs"] == "inspect-mode"
    assert batch_job["if"] == (
        "needs.inspect-mode.outputs.uses_agentic != 'true'"
    )
    batch_checkout = next(
        step for step in steps if step.get("name") == "Checkout"
    )
    assert batch_checkout["with"]["persist-credentials"] is False
    assert steps[block_index]["if"] == (
        "steps.read_config.outputs.uses_agentic == 'true'"
    )
    read_config_script = steps[names.index("Read experiment config flags")]["run"]
    assert '"agentic_sandbox"' in read_config_script
    assert '"agentic_sandbox_v2"' in read_config_script
    credential_indices = [
        index
        for index, step in enumerate(steps)
        if (
            "azure/login" in str(step.get("uses", ""))
            or "HF_TOKEN" in str(step.get("env", {}))
            or "OPENAI_API_KEY" in str(step.get("env", {}))
        )
    ]
    assert credential_indices
    assert block_index < min(credential_indices)
    assert all(
        "${{ inputs." not in str(step.get("run", ""))
        for job in document["jobs"].values()
        for step in job.get("steps", [])
    )


def test_agentic_image_build_is_sha_bound_and_attested():
    _assert_actions_are_commit_pinned(BUILD_WORKFLOW)
    text = BUILD_WORKFLOW.read_text(encoding="utf-8")
    steps = _steps(BUILD_WORKFLOW)
    workflow = yaml.safe_load(BUILD_WORKFLOW.read_text(encoding="utf-8"))
    assert set(workflow[True]) == {"workflow_dispatch"}
    job = workflow["jobs"]["build-sandbox-image"]
    assert job["if"] == (
        "github.ref == 'refs/heads/main' && github.ref_protected == true"
    )
    assert all(
        not str(step.get("uses", "")).endswith(("@v3", "@v4", "@v6"))
        for step in steps
    )
    candidate = next(
        step for step in steps
        if step.get("name") == "Build agentic sandbox audit candidate"
    )
    agentic = next(
        step for step in steps
        if step.get("name") == "Build and push audited agentic sandbox image"
    )
    config = agentic["with"]
    base = next(
        step for step in steps
        if step.get("name") == "Build and push sandbox image"
    )
    lock_gate = next(
        step for step in steps
        if step.get("name") == "Require immutable dependency locks before publication"
    )
    checkout = next(
        step for step in steps if step.get("name") == "Checkout"
    )
    main_guard = next(
        step for step in steps
        if step.get("name") == "Verify protected main checkout"
    )

    assert "agentic.Dockerfile" in config["file"]
    assert (
        "BASE_IMAGE=ghcr.io/hyeonsangjeon/gdpval-sandbox@${{ steps.base_build.outputs.digest }}"
        in config["build-args"]
    )
    assert base["id"] == "base_build"
    assert "if" not in base
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    assert "refs/heads/main" in main_guard["run"]
    assert "GITHUB_REF_PROTECTED" in main_guard["run"]
    assert "git rev-parse HEAD" in main_guard["run"]
    assert steps.index(lock_gate) < steps.index(base)
    assert lock_gate["if"] == "${{ inputs.publish_agentic == true }}"
    assert "--hash=sha256:" in lock_gate["run"]
    assert "debian-packages.lock" in lock_gate["run"]
    assert "len(packages) < 100" in lock_gate["run"]
    assert "GDPVAL_LOCKED_DEBIAN_PACKAGES" in lock_gate["run"]
    assert "pip install --upgrade" in lock_gate["run"]
    dockerfile = (
        ROOT / "batch-runner" / "sandbox" / "Dockerfile"
    ).read_text(encoding="utf-8")
    assert re.search(r"^FROM python:3\.11-slim-bookworm@sha256:[0-9a-f]{64}$", dockerfile, re.MULTILINE)
    assert "COPY requirements.txt requirements-renderer.txt /tmp/" in dockerfile
    assert agentic["id"] == "agentic_build"
    assert config["provenance"] == "mode=max"
    assert config["sbom"] is True
    assert "batch-runner/sandbox/agentic.Dockerfile" in text
    candidate_audit = next(
        step for step in steps
        if step.get("name") == "Audit agentic sandbox candidate before publication"
    )
    published_audit = next(
        step for step in steps
        if step.get("name") == "Verify published agentic digest and attestations"
    )
    promote = next(
        step for step in steps
        if step.get("name") == "Promote verified agentic digest to latest"
    )
    assert all(
        step["if"] == "${{ inputs.publish_agentic == true }}"
        for step in (candidate, candidate_audit, agentic, published_audit, promote)
    )
    assert candidate["with"]["load"] is True
    assert candidate["with"]["push"] is False
    assert "agentic_image_audit.py" in candidate_audit["run"]
    assert "steps.agentic_build.outputs.digest" in published_audit["env"]["IMAGE"]
    assert "steps.base_build.outputs.digest" in published_audit["env"]["EXPECTED_BASE"]
    assert "agentic-sbom.spdx.json" in published_audit["run"]
    assert "attached-sbom.json" in published_audit["run"]
    assert "imagetools create" in promote["run"]
    assert steps.index(candidate_audit) < steps.index(agentic)
    assert steps.index(published_audit) < steps.index(promote)


def test_agentic_preflight_is_dedicated_and_model_free():
    _assert_actions_are_commit_pinned(PREFLIGHT_WORKFLOW)
    document = yaml.safe_load(PREFLIGHT_WORKFLOW.read_text(encoding="utf-8"))
    job = document["jobs"]["model-free-preflight"]
    text = PREFLIGHT_WORKFLOW.read_text(encoding="utf-8")

    assert job["runs-on"] == ["self-hosted", "linux", "x64", "agentic-sandbox"]
    assert job["if"] == (
        "github.ref == 'refs/heads/main' && github.ref_protected == true"
    )
    assert document["permissions"] == {"contents": "read"}
    assert "azure/login" not in text
    assert "HF_TOKEN: ${{" not in text
    assert "OPENAI_API_KEY: ${{" not in text
    assert "pip install" not in text
    assert "setup-python" not in text
    assert "preloaded-model-free-environment=pass" in text
    assert "test_agentic_production_runner_preflight" in text
    assert (
        "test_outer_seccomp_allows_inner_filter_and_blocks_raw_signal_syscalls"
        in text
    )
    checkout = next(
        step for step in job["steps"] if step.get("name") == "Checkout exact implementation"
    )
    assert checkout["with"]["persist-credentials"] is False
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    main_guard = next(
        step for step in job["steps"]
        if step.get("name") == "Verify protected main checkout"
    )
    assert "refs/heads/main" in main_guard["run"]
    assert "GITHUB_REF_PROTECTED" in main_guard["run"]
    assert "git rev-parse HEAD" in main_guard["run"]