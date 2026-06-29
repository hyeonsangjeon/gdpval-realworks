"""Per-task Dependency Resolver for the sandbox.

Answers: *"which pip packages does this GDPVal task need?"* by combining three
signals:

1. **Reference-file extensions** — e.g. a ``.mp4`` implies opencv/av/moviepy,
   a ``.wav`` implies librosa/soundfile, a ``.pdf`` implies pdfplumber/PyMuPDF.
2. **Task-text keywords** — e.g. "spectrogram" → librosa, "regression" →
   scikit-learn, "shapefile" → geopandas.
3. **Imports in the generated code** — AST scan of ``solution.py`` mapped from
   import name to pip name (``cv2`` → opencv-python, ``fitz`` → PyMuPDF, …).

Each discovered package is classified against the sandbox base image's
``requirements.txt`` so the runner can warn when a task needs something the
image does not provide (``missing_from_base``).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

REQUIREMENTS_TXT = Path(__file__).resolve().parent.parent / "requirements.txt"

# Universally-present packages (transitive deps of the scientific stack and the
# interpreter toolchain). Treated as base even if not pinned in requirements.txt
# so the resolver never false-flags numpy as "missing from the image".
_IMPLICIT_BASE = {"numpy", "pip", "setuptools", "wheel"}

# ── import-name → pip-name (only where they differ) ───────────────────────────
IMPORT_TO_PIP: Dict[str, str] = {
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "fitz": "PyMuPDF",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "sklearn": "scikit-learn",
    "skimage": "scikit-image",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "pyzbar": "pyzbar",
    "numpy_financial": "numpy-financial",
    "dateutil": "python-dateutil",
    "Crypto": "pycryptodome",
    "OpenSSL": "pyOpenSSL",
    "fuzzywuzzy": "fuzzywuzzy",
    "rapidfuzz": "rapidfuzz",
    "google": "protobuf",
    "av": "av",
    "moviepy": "moviepy",
    "librosa": "librosa",
    "soundfile": "soundfile",
    "pydub": "pydub",
    "pyloudnorm": "pyloudnorm",
    "geopandas": "geopandas",
    "shapely": "shapely",
    "fiona": "fiona",
    "rasterio": "rasterio",
    "folium": "folium",
    "networkx": "networkx",
    "statsmodels": "statsmodels",
    "nltk": "nltk",
    "h5py": "h5py",
    "tables": "tables",
    "lxml": "lxml",
    "ezdxf": "ezdxf",
    "qrcode": "qrcode",
    "pytesseract": "pytesseract",
    "reportlab": "reportlab",
    "openpyxl": "openpyxl",
    "pdfplumber": "pdfplumber",
}

# ── reference-file extension → pip packages ──────────────────────────────────
EXT_PACKAGES: Dict[str, List[str]] = {
    # audio
    ".wav": ["librosa", "soundfile", "numpy", "scipy", "pyloudnorm"],
    ".mp3": ["librosa", "soundfile", "numpy", "pydub"],
    ".flac": ["librosa", "soundfile", "numpy"],
    ".ogg": ["librosa", "soundfile", "numpy"],
    ".m4a": ["librosa", "soundfile", "pydub"],
    ".aac": ["librosa", "pydub"],
    ".aiff": ["librosa", "soundfile"],
    # video
    ".mp4": ["opencv-python", "av", "moviepy", "numpy", "Pillow"],
    ".mov": ["opencv-python", "av", "moviepy", "numpy", "Pillow"],
    ".avi": ["opencv-python", "av", "moviepy", "numpy"],
    ".mkv": ["opencv-python", "av", "moviepy"],
    ".webm": ["opencv-python", "av", "moviepy"],
    ".m4v": ["opencv-python", "av", "moviepy"],
    ".mpg": ["opencv-python", "av"],
    ".mpeg": ["opencv-python", "av"],
    # image
    ".png": ["Pillow", "numpy"],
    ".jpg": ["Pillow", "numpy"],
    ".jpeg": ["Pillow", "numpy"],
    ".webp": ["Pillow"],
    ".bmp": ["Pillow"],
    ".tiff": ["Pillow"],
    ".tif": ["Pillow"],
    ".gif": ["Pillow"],
    # documents
    ".pdf": ["pdfplumber", "PyMuPDF", "reportlab"],
    ".docx": ["python-docx"],
    ".doc": ["python-docx"],
    ".pptx": ["python-pptx"],
    ".ppt": ["python-pptx"],
    ".xlsx": ["openpyxl", "pandas"],
    ".xls": ["xlrd", "pandas"],
    ".rtf": ["pypandoc"],
    ".odt": ["odfpy"],
    # data
    ".csv": ["pandas"],
    ".tsv": ["pandas"],
    ".parquet": ["pandas", "pyarrow"],
    ".json": [],
    ".xml": ["lxml"],
    ".h5": ["h5py", "tables"],
    ".hdf5": ["h5py", "tables"],
    # geo / cad
    ".shp": ["geopandas", "shapely", "fiona"],
    ".geojson": ["geopandas", "shapely"],
    ".kml": ["geopandas", "fiona"],
    ".gpkg": ["geopandas", "fiona"],
    ".dxf": ["ezdxf"],
    ".dwg": ["ezdxf"],
    # archives
    ".rar": ["rarfile"],
}

# ── task-text keyword → pip packages ─────────────────────────────────────────
KEYWORD_PACKAGES: Dict[str, List[str]] = {
    "spectrogram": ["librosa", "matplotlib"],
    "fft": ["numpy", "scipy"],
    "frequency": ["librosa", "scipy"],
    "loudness": ["pyloudnorm"],
    "lufs": ["pyloudnorm"],
    "tempo": ["librosa"],
    "bpm": ["librosa"],
    "waveform": ["librosa", "soundfile"],
    "resample": ["librosa"],
    "transcribe": ["librosa"],
    "keyframe": ["opencv-python", "moviepy"],
    "frame-by-frame": ["opencv-python"],
    "storyboard": ["opencv-python", "Pillow"],
    "scene": ["opencv-python"],
    "subtitle": ["srt"],
    "ocr": ["pytesseract"],
    "qr": ["pyzbar", "qrcode"],
    "barcode": ["pyzbar"],
    "regression": ["scikit-learn", "statsmodels"],
    "forecast": ["statsmodels", "scikit-learn"],
    "cluster": ["scikit-learn"],
    "classification": ["scikit-learn"],
    "machine learning": ["scikit-learn"],
    "correlation": ["pandas", "numpy"],
    "chart": ["matplotlib"],
    "plot": ["matplotlib"],
    "visualiz": ["matplotlib", "seaborn"],
    "heatmap": ["seaborn", "matplotlib"],
    "shapefile": ["geopandas", "shapely"],
    "geospatial": ["geopandas", "folium"],
    "map": ["folium"],
    "latitude": ["geopandas"],
    "pivot": ["pandas"],
    "dataframe": ["pandas"],
    "sentiment": ["nltk", "textblob"],
    "tokeniz": ["nltk"],
    "network graph": ["networkx"],
    "npv": ["numpy-financial"],
    "irr": ["numpy-financial"],
    "amortization": ["numpy-financial"],
}

# stdlib / always-present modules we never treat as a dependency.
_STDLIB_SKIP = {
    "os", "sys", "re", "json", "math", "csv", "io", "time", "datetime",
    "pathlib", "collections", "itertools", "functools", "random", "string",
    "typing", "dataclasses", "subprocess", "shutil", "tempfile", "glob",
    "logging", "argparse", "base64", "hashlib", "struct", "wave", "zipfile",
    "statistics", "decimal", "fractions", "textwrap", "unicodedata", "html",
    "xml", "urllib", "http", "uuid", "warnings", "copy", "enum", "abc",
    "contextlib", "operator", "bisect", "heapq", "calendar", "pprint",
    "skills",  # our own injected package
}


def _normalize(name: str) -> str:
    """PEP 503 normalize a package name for comparison."""
    name = name.split("[", 1)[0]  # drop extras
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def load_base_packages(requirements_path: Optional[Path] = None) -> Set[str]:
    """Parse the sandbox base image's requirements.txt into normalized names."""
    path = Path(requirements_path) if requirements_path else REQUIREMENTS_TXT
    base: Set[str] = set()
    if not path.exists():
        return base
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # strip inline comment, env markers, version specifiers
        line = line.split("#", 1)[0].strip()
        line = line.split(";", 1)[0].strip()
        token = re.split(r"[<>=!~\s\[]", line, maxsplit=1)[0]
        if token:
            base.add(_normalize(token))
    return base | _IMPLICIT_BASE


@dataclass
class DependencyManifest:
    """Result of resolving a single task's dependencies."""

    required: List[str] = field(default_factory=list)        # pip names, sorted
    sources: Dict[str, List[str]] = field(default_factory=dict)  # pkg -> reasons
    in_base: List[str] = field(default_factory=list)
    missing_from_base: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "required": self.required,
            "sources": self.sources,
            "in_base": self.in_base,
            "missing_from_base": self.missing_from_base,
        }

    def to_prompt_hint(self) -> str:
        if not self.required:
            return ""
        line = ", ".join(self.required)
        hint = f"📦 Likely libraries for this task (pre-installed): {line}"
        if self.missing_from_base:
            hint += (
                "\n⚠️  Not guaranteed in the sandbox image: "
                + ", ".join(self.missing_from_base)
                + " — prefer alternatives that are pre-installed."
            )
        return hint


def scan_imports(code: str) -> Set[str]:
    """Return the set of top-level modules imported by ``code``."""
    modules: Set[str] = set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Fall back to a regex scan on un-parseable / truncated code.
        for m in re.finditer(r"^\s*(?:import|from)\s+([A-Za-z0-9_\.]+)", code,
                             flags=re.MULTILINE):
            modules.add(m.group(1).split(".")[0])
        return {m for m in modules if m and m not in _STDLIB_SKIP}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                modules.add(node.module.split(".")[0])
    return {m for m in modules if m and m not in _STDLIB_SKIP}


def _pip_name_for_import(mod: str) -> str:
    return IMPORT_TO_PIP.get(mod, mod)


def resolve(
    reference_files: Optional[List[str]] = None,
    task_text: str = "",
    code: Optional[str] = None,
    base_packages: Optional[Set[str]] = None,
) -> DependencyManifest:
    """Resolve the pip packages a task is likely to need.

    Args:
        reference_files: paths whose extensions hint at modality libraries.
        task_text:       task instruction scanned for keyword triggers.
        code:            optional generated code scanned for imports.
        base_packages:   optional override of the base-image package set.
    """
    base = base_packages if base_packages is not None else load_base_packages()
    sources: Dict[str, List[str]] = {}

    def add(pkg: str, reason: str) -> None:
        sources.setdefault(pkg, [])
        if reason not in sources[pkg]:
            sources[pkg].append(reason)

    # 1) reference-file extensions
    for f in reference_files or []:
        ext = Path(f).suffix.lower()
        for pkg in EXT_PACKAGES.get(ext, []):
            add(pkg, f"ext:{ext}")

    # 2) task-text keywords
    text = (task_text or "").lower()
    for keyword, pkgs in KEYWORD_PACKAGES.items():
        if keyword in text:
            for pkg in pkgs:
                add(pkg, f"keyword:{keyword}")

    # 3) imports in generated code
    if code:
        for mod in scan_imports(code):
            add(_pip_name_for_import(mod), f"import:{mod}")

    required = sorted(sources.keys(), key=str.lower)
    in_base, missing = [], []
    for pkg in required:
        (in_base if _normalize(pkg) in base else missing).append(pkg)

    return DependencyManifest(
        required=required,
        sources=sources,
        in_base=in_base,
        missing_from_base=missing,
    )


# ── import-time probe (Part F) ───────────────────────────────────────────────
# pip-name → import-name, derived by inverting IMPORT_TO_PIP. Lets us actually
# *check* whether a predicted package can be imported in the execution env.
PIP_TO_IMPORT: Dict[str, str] = {pip: imp for imp, pip in IMPORT_TO_PIP.items()}


def _import_name_for_pip(pip_name: str) -> str:
    if pip_name in PIP_TO_IMPORT:
        return PIP_TO_IMPORT[pip_name]
    # Common convention: distribution dashes become import underscores.
    return pip_name.replace("-", "_")


@dataclass
class ImportProbe:
    """Result of probing whether predicted packages are importable here."""

    available: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    not_checked: List[str] = field(default_factory=list)
    env: str = "host"  # "host" (this interpreter) | "image" (informational)

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "missing": self.missing,
            "not_checked": self.not_checked,
            "env": self.env,
        }


def probe_imports(
    packages: List[str],
    finder=None,
    enabled: bool = True,
    env: str = "host",
) -> ImportProbe:
    """Probe importability of ``packages`` without importing them.

    Uses :func:`importlib.util.find_spec` (injectable via ``finder`` for tests).
    When ``enabled`` is False every package is reported ``not_checked`` — used for
    Docker execution, where the host interpreter cannot see the image's packages.
    """
    pkgs = sorted({p for p in (packages or []) if p})
    if not enabled:
        return ImportProbe(not_checked=pkgs, env=env)

    import importlib.util as _ilu
    find = finder or _ilu.find_spec

    available, missing, not_checked = [], [], []
    for pkg in pkgs:
        mod = _import_name_for_pip(pkg)
        try:
            spec = find(mod)
            (available if spec is not None else missing).append(pkg)
        except ModuleNotFoundError:
            missing.append(pkg)
        except Exception:
            not_checked.append(pkg)
    return ImportProbe(
        available=sorted(available),
        missing=sorted(missing),
        not_checked=sorted(not_checked),
        env=env,
    )
