"""Document skill toolkit — read & author PDF/DOCX/PPTX/XLSX/CSV.

Heavy libraries (pdfplumber, fitz/PyMuPDF, docx, pptx, openpyxl) are imported
lazily so importing this module never fails.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from skills import _require

__all__ = [
    "read_any",
    "read_pdf_text",
    "pdf_tables",
    "pdf_to_images",
    "read_docx",
    "read_pptx",
    "read_xlsx",
    "make_docx",
    "make_pdf",
    "make_pptx",
    "make_xlsx",
]


def read_any(path: str) -> str:
    """Auto-dispatch text extraction by file extension."""
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return read_pdf_text(path)
    if ext in (".docx", ".doc"):
        return read_docx(path)
    if ext in (".pptx", ".ppt"):
        return "\n\n".join(read_pptx(path))
    if ext in (".xlsx", ".xls"):
        rows = read_xlsx(path)
        return "\n\n".join(
            f"# {sheet}\n" + "\n".join("\t".join(str(c) for c in r) for r in data)
            for sheet, data in rows.items()
        )
    if ext == ".csv":
        return Path(path).read_text(encoding="utf-8", errors="replace")
    return Path(path).read_text(encoding="utf-8", errors="replace")


def read_pdf_text(path: str) -> str:
    pdfplumber = _require("pdfplumber", "pdfplumber")
    out: List[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return "\n\n".join(out)


def pdf_tables(path: str) -> List[List[List]]:
    """Return a list (one per page) of extracted tables."""
    pdfplumber = _require("pdfplumber", "pdfplumber")
    tables: List[List[List]] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            for tbl in page.extract_tables() or []:
                tables.append(tbl)
    return tables


def pdf_to_images(path: str, out_dir: str = "pages", dpi: int = 150) -> List[str]:
    """Render each PDF page to a PNG via PyMuPDF; return saved paths."""
    import os

    fitz = _require("fitz", "PyMuPDF")
    os.makedirs(out_dir, exist_ok=True)
    saved: List[str] = []
    doc = fitz.open(str(path))
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat)
        out = os.path.join(out_dir, f"page_{i + 1:03d}.png")
        pix.save(out)
        saved.append(out)
    doc.close()
    return saved


def read_docx(path: str) -> str:
    docx = _require("docx", "python-docx")
    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def read_pptx(path: str) -> List[str]:
    pptx = _require("pptx", "python-pptx")
    prs = pptx.Presentation(str(path))
    slides: List[str] = []
    for slide in prs.slides:
        texts = [shape.text for shape in slide.shapes if shape.has_text_frame]
        slides.append("\n".join(texts))
    return slides


def read_xlsx(path: str) -> Dict[str, List[list]]:
    openpyxl = _require("openpyxl", "openpyxl")
    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    out: Dict[str, List[list]] = {}
    for ws in wb.worksheets:
        out[ws.title] = [list(row) for row in ws.iter_rows(values_only=True)]
    wb.close()
    return out


def make_docx(title: str, paragraphs: List[str], out: str) -> str:
    docx = _require("docx", "python-docx")
    doc = docx.Document()
    doc.add_heading(title, 0)
    for para in paragraphs:
        doc.add_paragraph(para)
    doc.save(out)
    return out


def make_pdf(title: str, lines: List[str], out: str) -> str:
    _require("reportlab", "reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(out, pagesize=letter)
    flow = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
    for line in lines:
        flow.append(Paragraph(line, styles["BodyText"]))
        flow.append(Spacer(1, 6))
    doc.build(flow)
    return out


def make_pptx(title: str, slides: List[tuple], out: str) -> str:
    """slides = [(heading, [bullet, ...]), ...]."""
    pptx = _require("pptx", "python-pptx")
    prs = pptx.Presentation()
    title_layout = prs.slide_layouts[0]
    s = prs.slides.add_slide(title_layout)
    s.shapes.title.text = title
    bullet_layout = prs.slide_layouts[1]
    for heading, bullets in slides:
        slide = prs.slides.add_slide(bullet_layout)
        slide.shapes.title.text = heading
        body = slide.placeholders[1].text_frame
        for i, b in enumerate(bullets):
            (body.paragraphs[0] if i == 0 else body.add_paragraph()).text = str(b)
    prs.save(out)
    return out


def make_xlsx(sheets: Dict[str, List[list]], out: str) -> str:
    """sheets = {sheet_name: [[row], [row], ...]}."""
    openpyxl = _require("openpyxl", "openpyxl")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(title=str(name)[:31])
        for row in rows:
            ws.append(list(row))
    wb.save(out)
    return out
