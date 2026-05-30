"""``read_deliverable`` — read-only file inspection tool for the v2 grader.

Implements the 6-op surface from SPEC §4.2:

    inspect_structure / read_content / inspect_formatting
    render_to_image   / probe_audio   / probe_video

Design rules (per task spec 201):

1. All ops are read-only. They MUST NOT mutate files.
2. Paths are normalized against a trusted ``base_dir`` to prevent the
   judge from escaping out of the deliverables tree (no ``../`` traversal,
   no absolute paths that leave the base, no symlinks pointing outside).
3. Every op returns a uniform envelope:

       {"ok": True,  "data": <op-specific dict>}
       {"ok": False, "error": "<short reason>", "error_type": "<enum>"}

   Tool-calling judges serialize this directly back to JSON.
4. Large outputs (image bytes, raw content) are size-capped so the judge
   cannot accidentally inflate context by asking for a huge file.
5. Pure-Python fallbacks are preferred over system binaries. PDF
   rendering uses ``PyMuPDF`` (fitz), not poppler. Audio/video probing
   uses ``PyAV`` (``av``), not the ``ffmpeg`` binary. See
   ``tasks/rebuilding_grading_task/PR2_ENV_AUDIT.md`` for the rationale.
"""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ── Constants ─────────────────────────────────────────────────────────

#: Operations the judge is allowed to invoke.
READ_DELIVERABLE_OPS: Tuple[str, ...] = (
    "inspect_structure",
    "read_content",
    "inspect_formatting",
    "render_to_image",
    "probe_audio",
    "probe_video",
)

#: Output size caps. The tool refuses to return more than this in a
#: single call. These bound prompt growth, not file size on disk.
MAX_CONTENT_CHARS = 200_000   # ``read_content`` text payload cap
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB before/after downsample
MAX_CELLS_FORMATTING = 5_000  # inspect_formatting iterates capped cells
MAX_PAGES_DEFAULT = 200       # PDF page-iteration safety cap
MAX_SHEETS = 100              # workbook safety cap

#: JSON-schema fragment the Responses-API tool-calling judge gets in its
#: ``tools=[...]`` parameter. The judge sees these arg names verbatim.
READ_DELIVERABLE_TOOL_SCHEMA: Dict[str, Any] = {
    "type": "function",
    "name": "read_deliverable",
    "description": (
        "Read-only inspection of a deliverable file produced by the model "
        "under test. Use this to verify structure, content, formatting, "
        "or to render pages to images for visual judgment. NEVER fabricate "
        "file contents — always call this tool to ground evidence quotes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "op": {
                "type": "string",
                "enum": list(READ_DELIVERABLE_OPS),
                "description": (
                    "Operation to perform. "
                    "inspect_structure: file type + sheets/pages/slides summary. "
                    "read_content: textual content (no truncation up to cap). "
                    "inspect_formatting: cell fills/fonts/borders/charts/styles. "
                    "render_to_image: PNG (base64) of a page/sheet for vision. "
                    "probe_audio: sample-rate/channels/duration/peak/silence. "
                    "probe_video: codec/duration/resolution/fps."
                ),
            },
            "path": {
                "type": "string",
                "description": "Path relative to the deliverables base dir.",
            },
            "scope": {
                "type": ["object", "null"],
                "description": (
                    "Optional op-specific scope, e.g. "
                    "{'sheet': 'Summary'} or {'page': 1} or "
                    "{'page_start': 1, 'page_end': 3}."
                ),
                "additionalProperties": True,
            },
        },
        "required": ["op", "path"],
        "additionalProperties": False,
    },
}


# ── Errors / path safety ─────────────────────────────────────────────


class ReadDeliverableError(Exception):
    """Raised for non-recoverable misuse (programmer error)."""


def _envelope_error(msg: str, kind: str = "error") -> Dict[str, Any]:
    return {"ok": False, "error": msg, "error_type": kind}


def _envelope_ok(data: Any) -> Dict[str, Any]:
    return {"ok": True, "data": data}


def _resolve_trusted_path(path: str, base_dir: str) -> Optional[Path]:
    """Return the resolved path iff it lives inside ``base_dir``.

    Rejects: absolute paths outside base, ``..`` traversal, symlinks
    pointing outside base, missing files.
    """
    if not path or not isinstance(path, str):
        return None
    base = Path(base_dir).resolve()
    candidate = Path(path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (base / candidate).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None
    return resolved


# ── File type detection ──────────────────────────────────────────────


_EXT_KIND = {
    ".xlsx": "xlsx", ".xlsm": "xlsx",
    ".docx": "docx",
    ".pptx": "pptx",
    ".pdf": "pdf",
    ".csv": "csv",
    ".txt": "txt", ".md": "txt",
    ".json": "txt",
    ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".gif": "image", ".bmp": "image", ".webp": "image",
    ".wav": "audio", ".mp3": "audio", ".flac": "audio",
    ".ogg": "audio", ".m4a": "audio", ".aac": "audio",
    ".mp4": "video", ".mov": "video", ".webm": "video",
    ".mkv": "video", ".avi": "video",
}


def _kind_of(path: Path) -> str:
    return _EXT_KIND.get(path.suffix.lower(), "unknown")


# ── inspect_structure ────────────────────────────────────────────────


def _inspect_xlsx(p: Path) -> Dict[str, Any]:
    import openpyxl  # type: ignore

    wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
    sheets = []
    for name in wb.sheetnames[:MAX_SHEETS]:
        ws = wb[name]
        sheets.append({
            "name": name,
            "max_row": ws.max_row,
            "max_col": ws.max_column,
        })
    return {
        "kind": "xlsx",
        "sheet_count": len(wb.sheetnames),
        "sheets": sheets,
        "truncated": len(wb.sheetnames) > MAX_SHEETS,
    }


def _inspect_docx(p: Path) -> Dict[str, Any]:
    from docx import Document  # type: ignore

    doc = Document(str(p))
    return {
        "kind": "docx",
        "paragraph_count": len(doc.paragraphs),
        "table_count": len(doc.tables),
        "section_count": len(doc.sections),
        "styles_sample": sorted({p.style.name for p in doc.paragraphs[:200]
                                 if p.style is not None})[:20],
    }


def _inspect_pptx(p: Path) -> Dict[str, Any]:
    from pptx import Presentation  # type: ignore

    pres = Presentation(str(p))
    slides = []
    for i, slide in enumerate(pres.slides, 1):
        slides.append({
            "index": i,
            "shape_count": len(slide.shapes),
            "layout_name": getattr(slide.slide_layout, "name", None),
        })
    return {"kind": "pptx", "slide_count": len(pres.slides), "slides": slides}


def _inspect_pdf(p: Path) -> Dict[str, Any]:
    try:
        import fitz  # type: ignore
    except ImportError:
        import pdfplumber  # type: ignore
        with pdfplumber.open(p) as pdf:
            return {"kind": "pdf", "page_count": len(pdf.pages)}
    doc = fitz.open(str(p))
    try:
        return {
            "kind": "pdf",
            "page_count": doc.page_count,
            "metadata": dict(doc.metadata or {}),
        }
    finally:
        doc.close()


def _inspect_audio(p: Path) -> Dict[str, Any]:
    return _probe_audio_impl(p, basic=True)


def _inspect_video(p: Path) -> Dict[str, Any]:
    return _probe_video_impl(p, basic=True)


def _op_inspect_structure(p: Path, _scope: Dict[str, Any]) -> Dict[str, Any]:
    kind = _kind_of(p)
    size = p.stat().st_size
    base = {"kind": kind, "size_bytes": size, "filename": p.name}
    try:
        if kind == "xlsx":
            base.update(_inspect_xlsx(p))
        elif kind == "docx":
            base.update(_inspect_docx(p))
        elif kind == "pptx":
            base.update(_inspect_pptx(p))
        elif kind == "pdf":
            base.update(_inspect_pdf(p))
        elif kind == "audio":
            base["audio"] = _inspect_audio(p)
        elif kind == "video":
            base["video"] = _inspect_video(p)
        # txt/csv/image: size + kind only
    except Exception as exc:  # noqa: BLE001
        base["inspection_error"] = f"{type(exc).__name__}: {exc}"
    return base


# ── read_content ─────────────────────────────────────────────────────


def _read_xlsx_text(p: Path, scope: Dict[str, Any]) -> str:
    import openpyxl  # type: ignore

    wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
    target = scope.get("sheet")
    parts: List[str] = []
    for name in wb.sheetnames[:MAX_SHEETS]:
        if target is not None and name != target:
            continue
        ws = wb[name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append(",".join("" if c is None else str(c) for c in row))
        parts.append(f"[Sheet: {name}]\n" + "\n".join(rows))
        if sum(len(x) for x in parts) > MAX_CONTENT_CHARS:
            break
    return "\n\n".join(parts)


def _read_pdf_text(p: Path, scope: Dict[str, Any]) -> str:
    import pdfplumber  # type: ignore

    page_start = int(scope.get("page_start", 1))
    page_end = int(scope.get("page_end", MAX_PAGES_DEFAULT))
    parts: List[str] = []
    with pdfplumber.open(p) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            if i < page_start or i > page_end:
                continue
            txt = page.extract_text() or ""
            if txt.strip():
                parts.append(f"[Page {i}]\n{txt.strip()}")
            if sum(len(x) for x in parts) > MAX_CONTENT_CHARS:
                break
    return "\n\n".join(parts)


def _read_docx_text(p: Path, _scope: Dict[str, Any]) -> str:
    from docx import Document  # type: ignore

    doc = Document(str(p))
    parts = [para.text for para in doc.paragraphs if para.text.strip()]
    for tbl in doc.tables:
        rows = []
        for row in tbl.rows:
            rows.append(" | ".join(cell.text.strip() for cell in row.cells))
        parts.append("[Table]\n" + "\n".join(rows))
    return "\n\n".join(parts)


def _read_pptx_text(p: Path, _scope: Dict[str, Any]) -> str:
    from pptx import Presentation  # type: ignore

    pres = Presentation(str(p))
    parts: List[str] = []
    for i, slide in enumerate(pres.slides, 1):
        chunks = [f"[Slide {i}]"]
        for shape in slide.shapes:
            if shape.has_text_frame:
                t = shape.text_frame.text.strip()
                if t:
                    chunks.append(t)
        parts.append("\n".join(chunks))
        if sum(len(x) for x in parts) > MAX_CONTENT_CHARS:
            break
    return "\n\n".join(parts)


def _op_read_content(p: Path, scope: Dict[str, Any]) -> Dict[str, Any]:
    kind = _kind_of(p)
    if kind == "xlsx":
        text = _read_xlsx_text(p, scope)
    elif kind == "pdf":
        text = _read_pdf_text(p, scope)
    elif kind == "docx":
        text = _read_docx_text(p, scope)
    elif kind == "pptx":
        text = _read_pptx_text(p, scope)
    elif kind in ("txt", "csv"):
        text = p.read_text(encoding="utf-8", errors="replace")
    else:
        return {"kind": kind, "text": "", "note": "binary or unsupported for text read"}
    truncated = len(text) > MAX_CONTENT_CHARS
    if truncated:
        text = text[:MAX_CONTENT_CHARS]
    return {"kind": kind, "text": text, "char_count": len(text), "truncated": truncated}


# ── inspect_formatting ───────────────────────────────────────────────


def _format_xlsx(p: Path, scope: Dict[str, Any]) -> Dict[str, Any]:
    import openpyxl  # type: ignore

    wb = openpyxl.load_workbook(p, data_only=False)
    target = scope.get("sheet")
    sheets_meta = []
    for name in wb.sheetnames[:MAX_SHEETS]:
        if target is not None and name != target:
            continue
        ws = wb[name]
        merged = [str(r) for r in ws.merged_cells.ranges]
        col_widths = {k: (d.width if d.width is not None else None)
                      for k, d in ws.column_dimensions.items()}
        styled_cells: List[Dict[str, Any]] = []
        seen = 0
        for row in ws.iter_rows():
            for cell in row:
                if seen >= MAX_CELLS_FORMATTING:
                    break
                seen += 1
                if cell.value is None:
                    continue
                fill_color = None
                if cell.fill and cell.fill.fgColor and cell.fill.fgColor.rgb:
                    fill_color = str(cell.fill.fgColor.rgb)
                font_bold = bool(cell.font and cell.font.bold)
                font_color = (str(cell.font.color.rgb)
                              if cell.font and cell.font.color
                              and cell.font.color.rgb else None)
                has_border = bool(cell.border and (
                    (cell.border.top and cell.border.top.style) or
                    (cell.border.bottom and cell.border.bottom.style) or
                    (cell.border.left and cell.border.left.style) or
                    (cell.border.right and cell.border.right.style)
                ))
                if (fill_color and fill_color != "00000000") or font_bold \
                        or font_color or has_border:
                    styled_cells.append({
                        "ref": cell.coordinate,
                        "fill": fill_color,
                        "bold": font_bold,
                        "font_color": font_color,
                        "border": has_border,
                    })
            if seen >= MAX_CELLS_FORMATTING:
                break
        sheets_meta.append({
            "name": name,
            "merged_ranges": merged,
            "column_widths": col_widths,
            "has_charts": bool(getattr(ws, "_charts", [])),
            "styled_cells_sample": styled_cells[:50],
            "styled_cells_count": len(styled_cells),
            "cells_scanned": seen,
            "cells_scan_capped": seen >= MAX_CELLS_FORMATTING,
        })
    return {"kind": "xlsx", "sheets": sheets_meta}


def _format_docx(p: Path, _scope: Dict[str, Any]) -> Dict[str, Any]:
    from docx import Document  # type: ignore

    doc = Document(str(p))
    styles = {}
    for para in doc.paragraphs:
        if para.style is None:
            continue
        styles[para.style.name] = styles.get(para.style.name, 0) + 1
    return {
        "kind": "docx",
        "paragraph_count": len(doc.paragraphs),
        "table_count": len(doc.tables),
        "section_count": len(doc.sections),
        "style_histogram": styles,
    }


def _format_pptx(p: Path, _scope: Dict[str, Any]) -> Dict[str, Any]:
    from pptx import Presentation  # type: ignore

    pres = Presentation(str(p))
    slides = []
    for i, slide in enumerate(pres.slides, 1):
        shape_types: Dict[str, int] = {}
        for shape in slide.shapes:
            t = str(shape.shape_type)
            shape_types[t] = shape_types.get(t, 0) + 1
        slides.append({
            "index": i,
            "layout_name": getattr(slide.slide_layout, "name", None),
            "shape_types": shape_types,
        })
    return {"kind": "pptx", "slides": slides}


def _op_inspect_formatting(p: Path, scope: Dict[str, Any]) -> Dict[str, Any]:
    kind = _kind_of(p)
    if kind == "xlsx":
        return _format_xlsx(p, scope)
    if kind == "docx":
        return _format_docx(p, scope)
    if kind == "pptx":
        return _format_pptx(p, scope)
    if kind == "pdf":
        # PDF formatting probe stays light — PyMuPDF font enumeration.
        try:
            import fitz  # type: ignore
            doc = fitz.open(str(p))
            try:
                fonts = set()
                for page in doc:
                    for f in page.get_fonts(full=False):
                        fonts.add(f[3])
                return {"kind": "pdf", "page_count": doc.page_count,
                        "fonts": sorted(fonts)[:50]}
            finally:
                doc.close()
        except ImportError:
            return {"kind": "pdf", "note": "PyMuPDF not available"}
    return {"kind": kind, "note": "formatting inspection not supported for this kind"}


# ── render_to_image ──────────────────────────────────────────────────


def _png_bytes_from_pil(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _downsample_to_cap(png: bytes) -> bytes:
    if len(png) <= MAX_IMAGE_BYTES:
        return png
    from PIL import Image  # type: ignore
    img = Image.open(io.BytesIO(png))
    scale = (MAX_IMAGE_BYTES / len(png)) ** 0.5
    new_size = (max(64, int(img.width * scale)), max(64, int(img.height * scale)))
    img = img.resize(new_size, Image.LANCZOS)
    return _png_bytes_from_pil(img)


def _render_pdf_page(p: Path, page: int) -> bytes:
    import fitz  # type: ignore
    doc = fitz.open(str(p))
    try:
        if page < 1 or page > doc.page_count:
            raise ReadDeliverableError(
                f"page {page} out of range 1..{doc.page_count}")
        pix = doc.load_page(page - 1).get_pixmap(dpi=150)
        return pix.tobytes("png")
    finally:
        doc.close()


def _render_image(p: Path) -> bytes:
    from PIL import Image  # type: ignore
    return _png_bytes_from_pil(Image.open(p))


def _op_render_to_image(p: Path, scope: Dict[str, Any]) -> Dict[str, Any]:
    kind = _kind_of(p)
    if kind == "pdf":
        page = int(scope.get("page", 1))
        png = _render_pdf_page(p, page)
        png = _downsample_to_cap(png)
        return {
            "kind": "image_png_base64",
            "page": page,
            "base64": base64.b64encode(png).decode("ascii"),
            "byte_size": len(png),
        }
    if kind == "image":
        png = _downsample_to_cap(_render_image(p))
        return {
            "kind": "image_png_base64",
            "base64": base64.b64encode(png).decode("ascii"),
            "byte_size": len(png),
        }
    # xlsx/docx/pptx → would need LibreOffice headless; out of v2 scope.
    raise ReadDeliverableError(
        f"render_to_image not supported for kind={kind}; "
        "supported: pdf, image. Use inspect_structure/read_content instead."
    )


# ── probe_audio / probe_video ────────────────────────────────────────


def _probe_audio_impl(p: Path, basic: bool = False) -> Dict[str, Any]:
    """Use PyAV (wheel bundles ffmpeg) per env audit decision."""
    try:
        import av  # type: ignore
    except ImportError:
        return {"backend": "none", "note": "PyAV not installed"}

    container = av.open(str(p))
    try:
        if not container.streams.audio:
            return {"backend": "av", "error": "no audio stream"}
        stream = container.streams.audio[0]
        duration_s: Optional[float] = None
        if container.duration:
            duration_s = float(container.duration) / 1_000_000.0
        elif stream.duration and stream.time_base:
            duration_s = float(stream.duration * stream.time_base)
        info: Dict[str, Any] = {
            "backend": "av",
            "sample_rate": stream.sample_rate,
            "channels": stream.channels,
            "duration_s": duration_s,
            "codec": stream.codec.name if stream.codec else None,
        }
        if basic:
            return info

        # Peak + silence ratio across decoded frames (cap at ~120s scan)
        max_amp = 0.0
        silent_samples = 0
        total_samples = 0
        scan_limit_s = 120
        for frame in container.decode(audio=0):
            arr = frame.to_ndarray()
            if arr.size == 0:
                continue
            import math
            try:
                amp = float(abs(arr).max())
                if frame.format.is_packed:
                    # int16 → normalize
                    if arr.dtype.kind == "i":
                        amp /= float(2 ** (8 * arr.dtype.itemsize - 1))
                max_amp = max(max_amp, amp)
                # silence threshold = -40 dBFS
                threshold = 10 ** (-40 / 20)
                if arr.dtype.kind == "i":
                    norm = abs(arr) / float(2 ** (8 * arr.dtype.itemsize - 1))
                else:
                    norm = abs(arr)
                silent_samples += int((norm < threshold).sum())
                total_samples += int(arr.size)
            except Exception:  # noqa: BLE001
                pass
            if duration_s and frame.pts and frame.time_base \
                    and float(frame.pts * frame.time_base) > scan_limit_s:
                break
        info["peak_amplitude_normalized"] = max_amp
        info["clipping_suspected"] = max_amp >= 0.999
        info["silence_ratio"] = (silent_samples / total_samples) if total_samples else None
        info["scan_capped_seconds"] = scan_limit_s
        return info
    finally:
        container.close()


def _op_probe_audio(p: Path, _scope: Dict[str, Any]) -> Dict[str, Any]:
    kind = _kind_of(p)
    if kind != "audio":
        return {"kind": kind, "note": "not an audio file"}
    info = _probe_audio_impl(p, basic=False)
    info["kind"] = "audio"
    return info


def _probe_video_impl(p: Path, basic: bool = False) -> Dict[str, Any]:
    try:
        import av  # type: ignore
    except ImportError:
        return {"backend": "none", "note": "PyAV not installed"}
    container = av.open(str(p))
    try:
        if not container.streams.video:
            return {"backend": "av", "error": "no video stream"}
        vs = container.streams.video[0]
        duration_s = None
        if container.duration:
            duration_s = float(container.duration) / 1_000_000.0
        fps = None
        try:
            if vs.average_rate:
                fps = float(vs.average_rate)
        except Exception:  # noqa: BLE001
            pass
        return {
            "backend": "av",
            "codec": vs.codec.name if vs.codec else None,
            "width": vs.width,
            "height": vs.height,
            "fps": fps,
            "duration_s": duration_s,
            "audio_tracks": len(container.streams.audio),
            "video_tracks": len(container.streams.video),
        }
    finally:
        container.close()


def _op_probe_video(p: Path, _scope: Dict[str, Any]) -> Dict[str, Any]:
    kind = _kind_of(p)
    if kind != "video":
        return {"kind": kind, "note": "not a video file"}
    info = _probe_video_impl(p, basic=False)
    info["kind"] = "video"
    return info


# ── Public entrypoint ────────────────────────────────────────────────


_OP_TABLE = {
    "inspect_structure": _op_inspect_structure,
    "read_content": _op_read_content,
    "inspect_formatting": _op_inspect_formatting,
    "render_to_image": _op_render_to_image,
    "probe_audio": _op_probe_audio,
    "probe_video": _op_probe_video,
}


def read_deliverable(
    op: str,
    path: str,
    *,
    base_dir: str,
    scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch a read-only inspection op on a deliverable file.

    Args:
        op: One of ``READ_DELIVERABLE_OPS``.
        path: Path to the file. Resolved against ``base_dir``; traversal
              outside the base is rejected.
        base_dir: Trusted base directory (required keyword).
        scope: Op-specific scope dict (sheet name, page range, …).

    Returns:
        Envelope dict — see module docstring.
    """
    if op not in _OP_TABLE:
        return _envelope_error(
            f"unknown op {op!r}; allowed: {list(READ_DELIVERABLE_OPS)}",
            kind="bad_op",
        )
    resolved = _resolve_trusted_path(path, base_dir)
    if resolved is None:
        return _envelope_error(
            f"path {path!r} not found or escapes base_dir",
            kind="bad_path",
        )
    fn = _OP_TABLE[op]
    try:
        data = fn(resolved, scope or {})
        return _envelope_ok(data)
    except ReadDeliverableError as exc:
        return _envelope_error(str(exc), kind="op_error")
    except ImportError as exc:
        return _envelope_error(
            f"required library missing: {exc.name}",
            kind="dependency_missing",
        )
    except Exception as exc:  # noqa: BLE001
        return _envelope_error(
            f"{type(exc).__name__}: {exc}",
            kind="exception",
        )
