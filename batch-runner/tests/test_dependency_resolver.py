"""Tests for core/dependency_resolver.py"""

from pathlib import Path

import pytest

from core.dependency_resolver import (
    DependencyManifest,
    load_base_packages,
    resolve,
    scan_imports,
    _normalize,
)


# ── scan_imports ─────────────────────────────────────────────────────────

def test_scan_imports_basic():
    code = "import os\nimport cv2\nfrom librosa import load\nimport numpy as np"
    mods = scan_imports(code)
    assert "cv2" in mods
    assert "librosa" in mods
    assert "numpy" in mods
    assert "os" not in mods  # stdlib skipped


def test_scan_imports_skips_skills_package():
    code = "from skills.video.toolkit import extract_frames\nimport pandas"
    mods = scan_imports(code)
    assert "skills" not in mods
    assert "pandas" in mods


def test_scan_imports_relative_ignored():
    code = "from . import helper\nfrom .sub import thing\nimport scipy"
    mods = scan_imports(code)
    assert "scipy" in mods
    assert "helper" not in mods


def test_scan_imports_syntax_error_fallback():
    # Unparseable code still yields imports via regex fallback.
    code = "import cv2\nthis is not valid python <<<\nimport librosa"
    mods = scan_imports(code)
    assert "cv2" in mods
    assert "librosa" in mods


# ── load_base_packages ───────────────────────────────────────────────────

def test_load_base_packages_real_requirements():
    base = load_base_packages()
    assert "librosa" in base
    assert "opencv-python" in base
    assert "pandas" in base
    # implicit base always present even if only transitive
    assert "numpy" in base


def test_load_base_packages_custom_file(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text(
        "# comment\n"
        "Pillow>=10.0.0\n"
        "pandas==2.1.0  # inline comment\n"
        "lxml>=4.0; python_version>='3.8'\n"
        "-e .\n"
        "\n"
    )
    base = load_base_packages(req)
    assert "pillow" in base
    assert "pandas" in base
    assert "lxml" in base
    assert "numpy" in base  # implicit


def test_normalize():
    assert _normalize("opencv_python") == "opencv-python"
    assert _normalize("Pillow") == "pillow"
    assert _normalize("scikit-learn[extra]") == "scikit-learn"


# ── resolve ──────────────────────────────────────────────────────────────

def test_resolve_video_extension():
    m = resolve(reference_files=["/data/clip.mp4"], task_text="")
    assert "opencv-python" in m.required
    assert "av" in m.required
    assert "moviepy" in m.required
    assert any("ext:.mp4" in r for r in m.sources["opencv-python"])


def test_resolve_audio_keyword():
    m = resolve(reference_files=[], task_text="generate a spectrogram and measure loudness")
    assert "librosa" in m.required
    assert "pyloudnorm" in m.required
    assert any("keyword:" in r for r in m.sources["librosa"])


def test_resolve_code_imports():
    code = "import cv2\nimport fitz\nimport ezdxf"
    m = resolve(reference_files=[], task_text="", code=code)
    assert "opencv-python" in m.required  # cv2 -> opencv-python
    assert "PyMuPDF" in m.required        # fitz -> PyMuPDF
    assert "ezdxf" in m.required


def test_resolve_classifies_in_base_vs_missing():
    base = load_base_packages()
    # ezdxf is intentionally NOT in requirements.txt -> missing_from_base
    m = resolve(reference_files=["/x.dxf"], task_text="", base_packages=base)
    assert "ezdxf" in m.required
    assert "ezdxf" in m.missing_from_base
    assert "ezdxf" not in m.in_base


def test_resolve_numpy_not_falsely_missing():
    base = load_base_packages()
    m = resolve(reference_files=["/x.png"], task_text="", base_packages=base)
    assert "numpy" in m.required
    assert "numpy" in m.in_base
    assert "numpy" not in m.missing_from_base


def test_resolve_empty_task():
    m = resolve(reference_files=[], task_text="just write a poem")
    assert m.required == []
    assert m.to_prompt_hint() == ""


def test_manifest_to_prompt_hint_with_missing():
    base = load_base_packages()
    m = resolve(reference_files=["/x.dxf"], task_text="", base_packages=base)
    hint = m.to_prompt_hint()
    assert "ezdxf" in hint
    assert "Not guaranteed" in hint


def test_manifest_to_dict_keys():
    m = resolve(reference_files=["/a.csv"], task_text="")
    d = m.to_dict()
    assert set(d.keys()) == {"required", "sources", "in_base", "missing_from_base"}


def test_resolve_combines_all_three_signals():
    m = resolve(
        reference_files=["/data/clip.mp4"],
        task_text="extract keyframes",
        code="import pytesseract",
    )
    # ext signal
    assert "opencv-python" in m.required
    # keyword signal (keyframe -> opencv-python/moviepy)
    assert "moviepy" in m.required
    # import signal
    assert "pytesseract" in m.required
    assert any("import:pytesseract" in r for r in m.sources["pytesseract"])
