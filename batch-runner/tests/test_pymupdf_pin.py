"""The exp037 renderer version cannot float during exp038.

No package download, provider authentication or model call occurs in these
tests. CI's existing pip install supplies the distribution, whose installed
metadata AND a real in-memory PDF rasterization are checked below.
"""

from __future__ import annotations

import json
from importlib import metadata
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import yaml
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name, parse_wheel_filename


ROOT = Path(__file__).resolve().parents[2]
RENDERER = ROOT / "batch-runner/requirements-renderer.txt"
VERSIONS = {"3.10": "1.28.2", "3.11": "2.1", "3.12": "2.1", "3.13": "2.1"}
WHEEL_HASHES = {
    "2.1": "a9efa2e9e5f469d3b5749199329739cfef1ff1d1846538ced4885c544eecbcd9",
    "1.28.2": "397d6715c1f0df7548a92d0afd8ce370fc48fa47aeefac16be2bc04a16a8227f",
}


def _requirements() -> list[Requirement]:
    return [
        Requirement(line)
        for line in RENDERER.read_text(encoding="utf-8").splitlines()
        if line.startswith("PyMuPDF")
    ]


def _selected(environment: dict[str, str]) -> Requirement:
    matches = [
        requirement for requirement in _requirements()
        if requirement.marker is None or requirement.marker.evaluate(environment)
    ]
    assert len(matches) == 1, f"ambiguous/missing PyMuPDF pin: {matches}"
    assert canonicalize_name(matches[0].name) == "pymupdf"
    return matches[0]


def _pinned_version(requirement: Requirement) -> str:
    if requirement.url:
        name, version, _, _ = parse_wheel_filename(Path(urlsplit(requirement.url).path).name)
        assert name == "pymupdf"
        return str(version)
    pins = list(requirement.specifier)
    assert len(pins) == 1
    assert pins[0].operator == "==" and "*" not in pins[0].version
    return pins[0].version


@pytest.mark.parametrize("python_version", VERSIONS)
@pytest.mark.parametrize("system,machine", [
    ("linux", "x86_64"), ("linux", "aarch64"),
    ("darwin", "arm64"), ("darwin", "x86_64"), ("win32", "AMD64"),
])
def test_exactly_one_exact_pin_for_each_supported_python_and_platform(
    python_version, system, machine,
):
    environment = {
        **default_environment(), "python_version": python_version,
        "sys_platform": system, "platform_machine": machine,
    }
    requirement = _selected(environment)
    version = _pinned_version(requirement)
    assert version == VERSIONS[python_version]
    if system == "linux" and machine == "x86_64":
        url = urlsplit(requirement.url)
        assert url.scheme == "https" and url.hostname == "files.pythonhosted.org"
        assert parse_qs(url.fragment) == {"sha256": [WHEEL_HASHES[version]]}
        _, _, _, tags = parse_wheel_filename(Path(url.path).name)
        assert {tag.interpreter for tag in tags} == {"cp310" if version == "1.28.2" else "cp311"}
        assert {tag.abi for tag in tags} == {"abi3"}
        assert {tag.platform for tag in tags} == {"manylinux_2_28_x86_64"}
    else:
        assert requirement.url is None


def test_installed_distribution_and_renderer_match_the_selected_pin():
    # Do not importorskip: an absent/different renderer must fail CI.
    import fitz

    requirement = _selected(default_environment())
    expected = _pinned_version(requirement)
    distribution = metadata.distribution("PyMuPDF")
    assert distribution.version == expected
    assert fitz.VersionBind == expected
    assert Path(fitz.__file__).resolve().is_relative_to(distribution.locate_file("").resolve())
    if requirement.url:
        # pip's installation receipt must identify the hash-bound wheel, not
        # merely another distribution with the same version string.
        receipt = json.loads(distribution.read_text("direct_url.json") or "{}")
        url = urlsplit(requirement.url)
        assert receipt["url"] == url._replace(fragment="").geturl()
        assert receipt["archive_info"]["hashes"]["sha256"] == WHEEL_HASHES[expected]
    with fitz.open() as document:
        page = document.new_page(width=120, height=120)
        page.insert_text((12, 24), "pinned renderer")
        pixmap = page.get_pixmap()
        assert (pixmap.width, pixmap.height) == (120, 120)
        assert pixmap.tobytes("png").startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize("workflow_name,job_name,python_version", [
    ("grade-run.yml", "grade", "3.11"),
    ("grade-run.yml", "grade-dry-run", "3.11"),
    ("grade-run.yml", "verify-published", "3.10.12"),
    ("batch-run.yml", "batch-run", "3.11"),
])
def test_grade_and_batch_installs_reach_the_pin_without_moving_python(
    workflow_name, job_name, python_version,
):
    document = yaml.safe_load((ROOT / ".github/workflows" / workflow_name).read_text())
    steps = document["jobs"][job_name]["steps"]
    setup = next(step for step in steps if step.get("uses", "").startswith("actions/setup-python@"))
    declared = setup["with"]["python-version"]
    if declared == "${{ env.PYTHON_VERSION }}":
        declared = document["env"]["PYTHON_VERSION"]
    assert declared == python_version
    install = "\n".join(step.get("run", "") for step in steps)
    assert "pip install -r requirements.txt" in install or "pip install -r batch-runner/requirements.txt" in install
    assert "-r requirements-renderer.txt" in (ROOT / "batch-runner/requirements.txt").read_text().splitlines()
    environment = {
        **default_environment(),
        "python_version": ".".join(python_version.split(".")[:2]),
    }
    expected = "1.28.2" if python_version == "3.10.12" else "2.1"
    assert _pinned_version(_selected(environment)) == expected


def test_every_backend_job_keeps_python_310_and_installs_the_shared_pin():
    document = yaml.safe_load((ROOT / ".github/workflows/backend-tests.yml").read_text())
    assert document["jobs"]
    for job in document["jobs"].values():
        steps = job["steps"]
        setup = next(step for step in steps if step.get("uses", "").startswith("actions/setup-python@"))
        assert setup["with"]["python-version"] == "3.10.12"
        assert any("pip install -r requirements.txt" in step.get("run", "") for step in steps)
    requirement = _selected({**default_environment(), "python_version": "3.10"})
    assert _pinned_version(requirement) == "1.28.2"
