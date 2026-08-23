"""Static contract for the purpose-built grading image and its build workflow.

The image exists to stop the renderer moving under the judge, so the things
worth testing without Docker are the ones that would let it move anyway: a
version restated instead of derived, a package the runner installs and the
image does not, a floating base, a floating published tag, or a package
source trusted without checking who signed it.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from scripts import preflight_grading_renderer as preflight


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE_PATH = REPO_ROOT / "batch-runner/sandbox/grading.Dockerfile"
BUILD_WORKFLOW_PATH = REPO_ROOT / ".github/workflows/build-grading-image.yml"
GRADE_WORKFLOW_PATH = REPO_ROOT / ".github/workflows/grade-run.yml"

RENDERER_INSTALL_STEP = "Install grading render dependencies"
PINNED_ACTION = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


def _dockerfile() -> str:
    return DOCKERFILE_PATH.read_text(encoding="utf-8")


def _dockerfile_instructions() -> str:
    """The Dockerfile with comments dropped — what actually runs."""
    return "\n".join(
        line
        for line in _dockerfile().splitlines()
        if not line.lstrip().startswith("#")
    )


def _workflow(path: Path) -> dict:
    parsed = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(parsed, dict)
    return parsed


def _apt_packages(shell_text: str) -> set[str]:
    """Collect package names from every ``apt-get install`` in a snippet."""
    joined = " ".join(
        line.strip().rstrip("\\").strip() for line in shell_text.splitlines()
    )
    packages: set[str] = set()
    for segment in re.split(r"(?:&&|\|\||;)", joined):
        tokens = segment.split()
        if "install" not in tokens:
            continue
        if not any(token.endswith("apt-get") for token in tokens):
            continue
        for token in tokens[tokens.index("install") + 1:]:
            if token.startswith("-"):
                continue
            if re.fullmatch(r"[a-z0-9][a-z0-9+.-]*", token):
                packages.add(token)
    return packages


def _renderer_install_step() -> str:
    grade = _workflow(GRADE_WORKFLOW_PATH)
    for step in grade["jobs"]["grade"]["steps"]:
        if step.get("name") == RENDERER_INSTALL_STEP:
            return step["run"]
    raise AssertionError(f"{RENDERER_INSTALL_STEP!r} step not found in grade-run.yml")


def test_expected_renderer_version_is_derived_from_the_preflight_pin():
    # One source of truth. A second copy is how a renderer upgrade lands in
    # the image while the preflight still asserts the old build, which is a
    # failure that only shows up after a paid run has already been graded.
    match = re.search(
        r'^ARG EXPECTED_LIBREOFFICE_VERSION="(?P<value>[^"]+)"$',
        _dockerfile(),
        re.MULTILINE,
    )
    assert match is not None
    assert match.group("value") == preflight.EXPECTED_LIBREOFFICE_VERSION


def test_image_carries_every_package_the_runner_installs():
    image_packages = _apt_packages(_dockerfile_instructions())
    runner_packages = _apt_packages(_renderer_install_step())

    assert runner_packages, "renderer install step parsed to no packages"
    # Guards the parser as much as the image: if the extraction ever degrades
    # to a handful of tokens, the superset check below would pass vacuously.
    assert {"libreoffice-core", "fontconfig"} <= runner_packages
    assert runner_packages <= image_packages, sorted(runner_packages - image_packages)


def test_image_carries_the_actions_runtime_the_grade_job_needs():
    # Without git, actions/checkout falls back to a REST tarball with no .git
    # and the grade job's own checkout verification fails; without az,
    # azure/login cannot complete the OIDC exchange.
    image_packages = _apt_packages(_dockerfile_instructions())

    assert {"git", "curl", "ca-certificates", "azure-cli"} <= image_packages


def test_base_image_is_digest_pinned_to_ubuntu_2404():
    # ubuntu:24.04 is where the 24.2.7.2 renderer comes from; the digest is
    # what stops a rebuild picking up a later one.
    from_lines = [
        line.strip()
        for line in _dockerfile().splitlines()
        if line.startswith("FROM ")
    ]

    assert len(from_lines) == 1
    assert re.fullmatch(r"FROM ubuntu:24\.04@sha256:[0-9a-f]{64}", from_lines[0])


def test_build_asserts_the_renderer_rather_than_reporting_it():
    text = _dockerfile()

    assert 'actual="$(soffice --headless --version)"' in text
    assert 'if [ "$actual" != "$EXPECTED_LIBREOFFICE_VERSION" ]; then' in text
    assert "/opt/gdpval/renderer-version.txt" in text
    assert "grep -qx 'Liberation Sans'" in text


def test_azure_cli_source_is_verified_before_it_is_trusted():
    text = _dockerfile()
    fingerprint = re.search(
        r'^ARG MICROSOFT_GPG_FINGERPRINT="(?P<value>[^"]+)"$', text, re.MULTILINE
    )

    assert fingerprint is not None
    assert re.fullmatch(r"[0-9A-F]{40}", fingerprint.group("value"))
    assert 'if [ "$actual" != "$MICROSOFT_GPG_FINGERPRINT" ]; then' in text
    assert "signed-by=/usr/share/keyrings/microsoft.gpg" in text
    # The documented install path for azure-cli is a redirect piped into a
    # root shell. Nothing that *runs* here may reintroduce it — the prose
    # above the RUN step is allowed to name it, which is why this reads the
    # instructions rather than the file.
    instructions = _dockerfile_instructions()
    assert "aka.ms" not in instructions
    assert not re.search(r"\|\s*(ba)?sh\b", instructions)


def test_build_workflow_verifies_on_pull_request_without_pushing():
    workflow = _workflow(BUILD_WORKFLOW_PATH)
    triggers = workflow["on"]

    assert set(triggers) == {"workflow_dispatch", "pull_request"}
    assert "batch-runner/sandbox/grading.Dockerfile" in triggers["pull_request"]["paths"]
    assert workflow["permissions"] == {"contents": "read"}

    verify = workflow["jobs"]["verify-grading-image"]
    assert verify["permissions"] == {"contents": "read"}
    build = next(
        step for step in verify["steps"] if step.get("name") == "Build grading image"
    )
    assert build["with"]["push"] == "false"
    assert build["with"]["file"] == "batch-runner/sandbox/grading.Dockerfile"


def test_publish_is_gated_and_pinned_by_digest_not_by_tag():
    workflow = _workflow(BUILD_WORKFLOW_PATH)
    publish = workflow["jobs"]["publish-grading-image"]

    assert publish["permissions"] == {"contents": "read", "packages": "write"}
    for guard in (
        "inputs.publish == true",
        "github.ref == 'refs/heads/main'",
        "github.ref_protected == true",
    ):
        assert guard in publish["if"]

    build = next(
        step
        for step in publish["steps"]
        if step.get("name") == "Build and push grading image"
    )
    tags = build["with"]["tags"]
    # A moving :latest would let the renderer change under a grade job that
    # never changed, which is the whole failure this image exists to remove.
    assert ":latest" not in tags
    assert "${{ github.sha }}" in tags


def test_every_action_in_the_build_workflow_is_sha_pinned():
    workflow = _workflow(BUILD_WORKFLOW_PATH)
    uses = [
        step["uses"]
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "uses" in step
    ]

    assert uses
    unpinned = [reference for reference in uses if not PINNED_ACTION.fullmatch(reference)]
    assert not unpinned, unpinned
