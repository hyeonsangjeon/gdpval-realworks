"""Static security contract for the model-free renderer preflight workflow."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/grading-renderer-preflight.yml"
CHECKOUT = "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09"
SETUP_PYTHON = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
UPLOAD_ARTIFACT = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"


def _workflow() -> tuple[str, dict]:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    parsed = yaml.load(text, Loader=yaml.BaseLoader)
    assert isinstance(parsed, dict)
    return text, parsed


def test_workflow_is_manual_main_only_and_read_only():
    _, workflow = _workflow()

    assert workflow["on"] == {"workflow_dispatch": ""}
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "grading-renderer-preflight",
        "cancel-in-progress": "false",
    }
    assert set(workflow["jobs"]) == {"preflight"}
    job = workflow["jobs"]["preflight"]
    assert job["if"] == "github.ref == 'refs/heads/main'"
    assert job["runs-on"] == "ubuntu-24.04"
    assert job["timeout-minutes"] == "20"
    assert job["env"] == {"PYTHONDONTWRITEBYTECODE": "1"}
    assert "environment" not in job


def test_actions_are_allowlisted_and_pinned():
    _, workflow = _workflow()
    steps = workflow["jobs"]["preflight"]["steps"]
    actions = [step["uses"] for step in steps if "uses" in step]

    assert actions == [CHECKOUT, SETUP_PYTHON, UPLOAD_ARTIFACT]
    assert steps[0]["with"]["persist-credentials"] == "false"
    assert steps[1]["with"]["cache-dependency-path"] == (
        "batch-runner/requirements-renderer.txt"
    )
    upload = steps[-1]
    assert upload["if"] == "always()"
    assert upload["with"]["retention-days"] == "7"
    assert upload["with"]["if-no-files-found"] == "error"


def test_workflow_installs_only_renderer_surface_and_validates_json():
    text, workflow = _workflow()
    steps = workflow["jobs"]["preflight"]["steps"]
    runs = "\n".join(step.get("run", "") for step in steps)

    for package in (
        "libreoffice-core",
        "libreoffice-calc",
        "libreoffice-impress",
        # Writer is what renders .docx. Its absence is why the preflight could
        # pass while the judge could not render a document deliverable.
        "libreoffice-writer",
        "fonts-dejavu-core",
        "fonts-liberation2",
        "fontconfig",
    ):
        assert package in runs
    assert "batch-runner/requirements-renderer.txt" in runs
    assert "python scripts/preflight_grading_renderer.py" in runs
    assert 'payload.get("ok") is not True' in runs
    assert "$RUNNER_TEMP/grading-renderer-preflight.json" in runs

    lowered = text.lower()
    for forbidden in (
        "${{ secrets.",
        "id-token",
        "azure/login",
        "hf_token",
        "openai",
        "step8_grade",
        "git push",
        "git commit",
    ):
        assert forbidden not in lowered