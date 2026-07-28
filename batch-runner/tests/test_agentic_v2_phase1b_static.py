from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SANDBOX = ROOT / "batch-runner" / "sandbox"
V2 = SANDBOX / "v2"

V1_IDENTITIES = {
    SANDBOX / "Dockerfile": "a22f415d405969b6350e7c20f33bbc268539ba46a79b32dfb95c4e100d184e09",
    SANDBOX / "agentic.Dockerfile": "1c66310bddc316a6ec53b28a6d0f361b6cac95f0bcbe51d8b3584640f634c957",
    SANDBOX / "build_agentic.sh": "4fa24e74f5b420918917c3300ba2fb925c433eb518c5ae03a92b357d10db1a17",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_phase1b_does_not_change_v1_image_build_identity():
    assert {path: _sha256(path) for path in V1_IDENTITIES} == V1_IDENTITIES


def test_phase1b_candidate_has_no_mutable_parent_or_registry_path():
    dockerfile = (V2 / "professional-work.Dockerfile").read_text(encoding="utf-8")
    builder = (V2 / "build_candidate.py").read_text(encoding="utf-8")
    verifier = (V2 / "verify_candidate.py").read_text(encoding="utf-8")
    combined = "\n".join((dockerfile, builder, verifier))

    assert re.search(r"^ARG BASE_IMAGE$", dockerfile, re.MULTILINE)
    assert "foundation-only=\"true\"" in dockerfile
    assert "production-activation=\"disabled\"" in dockerfile
    assert "disabled_entrypoint.py" in dockerfile
    for forbidden in (
        "docker login",
        "docker push",
        "imagetools create",
        ":latest",
        "ghcr.io/" + "hyeonsangjeon/gdpval-agentic-v2",
    ):
        assert forbidden not in combined


def test_phase1b_parent_and_extra_locks_are_exact():
    parent = json.loads((V2 / "parent.lock.json").read_text(encoding="utf-8"))
    assert parent["reference"].endswith(parent["manifest_digest"])
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", parent["manifest_digest"])
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", parent["observed_local_image_id"])

    debian = [
        line for line in (V2 / "debian-extra.lock").read_text().splitlines()
        if line
    ]
    assert debian == sorted(debian)
    assert len(debian) == len(set(debian)) == 7
    assert all("=" in line and not any(character.isspace() for character in line) for line in debian)
    assert {line.split("=", 1)[0] for line in debian} == {
        "chromium", "cmake", "fonts-noto-color-emoji", "fonts-noto-core",
        "nodejs", "npm", "r-base-core",
    }

    python_lock = (V2 / "python-extra.lock").read_text(encoding="utf-8")
    assert "ezdxf==1.4.3" in python_lock
    assert "--hash=sha256:1f86db7aa4ee1103a0fdf565e6a710c9db13cdcf41c19f3f617c183e6959440b" in python_lock


def test_phase1b_does_not_add_workflow_or_execution_activation():
    workflows = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    )
    assert "agentic-v2-phase1b" not in workflows

    executor = (ROOT / "batch-runner" / "core" / "executor.py").read_text(encoding="utf-8")
    step2 = (ROOT / "batch-runner" / "step2_run_inference.py").read_text(encoding="utf-8")
    assert "AgenticV2IsolatedFixtureRunner" in executor
    assert "foundation is model-free only" in executor
    assert "scripted fixture harness" in step2