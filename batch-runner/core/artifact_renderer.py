"""Render generated artifacts to PNG snapshots — the solver's *eyes on output*.

GDPVal's "Overall Style" depends on how a deliverable actually *looks* once
opened. This module rasterizes generated PDFs / Office docs / images so the
output-QA layer (and, optionally, a vision model) can inspect appearance, and so
deterministic checks (blank-page / empty-canvas detection) can run with zero LLM
cost.

Strategy by kind:
* **pdf**      -> PyMuPDF renders the first N pages directly.
* **pptx/docx/xlsx** -> LibreOffice headless converts to PDF, then PyMuPDF.
* **image**    -> the original (optionally thumbnailed) is the snapshot.
* everything else is skipped with a note.

All heavy bits are lazily imported and failures become warnings, not crashes, so
the renderer is safe in a light venv (it simply produces fewer snapshots).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from core.artifact_verifier import classify_kind

_OFFICE_KINDS = {"spreadsheet", "document", "presentation"}
_RENDERABLE = _OFFICE_KINDS | {"pdf", "image"}


@dataclass
class RenderResult:
    rel_path: str
    kind: str
    page_count: int = 0
    rendered_images: List[str] = field(default_factory=list)
    blank_pages: List[int] = field(default_factory=list)
    page_white_fractions: List[float] = field(default_factory=list)
    converted_via: Optional[str] = None
    cached: bool = False
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _find_soffice() -> Optional[str]:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    mac = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if Path(mac).exists():
        return mac
    return None


def libreoffice_available() -> bool:
    return _find_soffice() is not None


def _blank_fraction(pix) -> float:
    """Fraction of near-white pixels in a grayscale PyMuPDF pixmap."""
    samples = pix.samples
    if not samples:
        return 1.0
    try:
        import numpy as np
        arr = np.frombuffer(samples, dtype=np.uint8)
        return float((arr >= 250).mean())
    except Exception:
        step = max(1, len(samples) // 4096)
        sampled = samples[::step]
        white = sum(1 for b in sampled if b >= 250)
        return white / max(len(sampled), 1)


def _render_pdf(
    pdf_path: Path, out_dir: Path, stem: str, max_pages: int,
    blank_threshold: float, dpi: int, result: RenderResult,
) -> None:
    try:
        import fitz
    except Exception:
        result.warnings.append("PyMuPDF unavailable; cannot render to PNG")
        return
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        result.errors.append(f"could not open PDF for render: {e}")
        return
    result.page_count = doc.page_count
    n = min(max_pages, doc.page_count)
    for i in range(n):
        try:
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=dpi)
            img_path = out_dir / f"{stem}_p{i + 1}.png"
            pix.save(str(img_path))
            result.rendered_images.append(str(img_path))
            gray = page.get_pixmap(dpi=72, colorspace=fitz.csGRAY)
            white = _blank_fraction(gray)
            result.page_white_fractions.append(round(white, 5))
            if white >= blank_threshold:
                result.blank_pages.append(i + 1)
        except Exception as e:
            result.warnings.append(f"page {i + 1} render failed: {e}")
    doc.close()


def _convert_office_to_pdf(src: Path, out_dir: Path, result: RenderResult) -> Optional[Path]:
    soffice = _find_soffice()
    if not soffice:
        result.warnings.append("LibreOffice unavailable; cannot render office document")
        return None
    try:
        proc = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir",
             str(out_dir), str(src)],
            capture_output=True, text=True, timeout=120,
        )
        pdf_path = out_dir / (src.stem + ".pdf")
        if pdf_path.exists():
            result.converted_via = "libreoffice"
            return pdf_path
        result.warnings.append(
            f"LibreOffice conversion produced no PDF: {proc.stderr[-200:]}"
        )
    except Exception as e:
        result.warnings.append(f"LibreOffice conversion failed: {e}")
    return None


def _render_image(src: Path, out_dir: Path, stem: str, result: RenderResult) -> None:
    try:
        from PIL import Image
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail((1600, 1600))
            img_path = out_dir / f"{stem}_p1.png"
            im.save(img_path)
            result.rendered_images.append(str(img_path))
            result.page_count = 1
    except Exception as e:
        result.warnings.append(f"image snapshot failed: {e}")


def render_artifact(
    artifact_path,
    out_dir,
    max_pages: int = 3,
    blank_threshold: float = 0.999,
    dpi: int = 120,
    cache=None,
) -> RenderResult:
    """Render one artifact to PNG snapshot(s) under ``out_dir``."""
    artifact_path = Path(artifact_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    kind = classify_kind(artifact_path.suffix)
    result = RenderResult(rel_path=artifact_path.name, kind=kind)

    if kind not in _RENDERABLE:
        result.warnings.append(f"kind '{kind}' is not rendered")
        return result
    if not artifact_path.exists() or artifact_path.stat().st_size == 0:
        result.errors.append("artifact missing or empty; nothing to render")
        return result

    stem = artifact_path.stem
    cfg = {"max_pages": max_pages, "blank_threshold": blank_threshold, "dpi": dpi}
    ckey = None
    if cache is not None and getattr(cache, "enabled", False):
        try:
            ckey = cache.key(cache.hash_file(artifact_path), "render", cfg)
            meta = cache.get_json(ckey)
            if meta:
                for i, b64name in enumerate(meta.get("image_keys", [])):
                    data = cache.get_bytes(b64name, suffix=".png")
                    if data:
                        img_path = out_dir / f"{stem}_p{i + 1}.png"
                        img_path.write_bytes(data)
                        result.rendered_images.append(str(img_path))
                result.page_count = meta.get("page_count", len(result.rendered_images))
                result.blank_pages = meta.get("blank_pages", [])
                result.page_white_fractions = meta.get("page_white_fractions", [])
                result.converted_via = meta.get("converted_via")
                result.cached = True
                return result
        except Exception:
            ckey = None

    if kind == "pdf":
        _render_pdf(artifact_path, out_dir, stem, max_pages, blank_threshold, dpi, result)
    elif kind == "image":
        _render_image(artifact_path, out_dir, stem, result)
    elif kind in _OFFICE_KINDS:
        pdf_path = _convert_office_to_pdf(artifact_path, out_dir, result)
        if pdf_path is not None:
            _render_pdf(pdf_path, out_dir, stem, max_pages, blank_threshold, dpi, result)

    if ckey is not None and result.rendered_images:
        try:
            image_keys = []
            for i, img in enumerate(result.rendered_images):
                page_key = f"{ckey}-p{i + 1}"
                cache.put_bytes(page_key, Path(img).read_bytes(), suffix=".png")
                image_keys.append(page_key)
            cache.put_json(ckey, {
                "page_count": result.page_count,
                "blank_pages": result.blank_pages,
                "page_white_fractions": result.page_white_fractions,
                "converted_via": result.converted_via,
                "image_keys": image_keys,
            })
        except Exception:
            pass

    return result
