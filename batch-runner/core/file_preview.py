"""
File Preview Generator — Create text previews of reference files for LLM context.

Subprocess mode cannot upload files to a sandbox like Code Interpreter.
Instead, this module reads reference files and generates concise text previews
that are injected into the LLM prompt so it can understand file contents before
generating code.

Supported formats:
- Excel (.xlsx, .xls)  — sheet names, columns, first N rows, row/column counts
- CSV (.csv)           — columns, first N rows, row count
- Word (.docx)         — full text extraction
- PDF (.pdf)           — text extraction via pdfplumber
- Text (.txt, .md, .json, .html, .xml, .yaml, .yml) — raw content
- Images (.png, .jpg, .jpeg, .webp) — dimensions and file size only
- Other formats        — file size and type info only

Usage:
    from core.file_preview import generate_all_previews

    previews = generate_all_previews(
        ["/path/to/data.xlsx", "/path/to/brief.pdf"],
        max_rows=10,
        max_chars=3000,
    )
    # Returns a formatted string block ready for prompt injection
"""

from pathlib import Path
from typing import List, Optional


# Limits
MAX_PREVIEW_ROWS = 10
MAX_PREVIEW_CHARS_PER_FILE = 3000
MAX_TOTAL_PREVIEW_CHARS = 10000


def generate_file_preview(
    file_path: str,
    max_rows: int = MAX_PREVIEW_ROWS,
    max_chars: int = MAX_PREVIEW_CHARS_PER_FILE,
) -> str:
    """
    Generate a text preview of a single reference file.

    Args:
        file_path: Absolute path to the file
        max_rows: Max rows to show for tabular data
        max_chars: Max characters for text content

    Returns:
        Formatted string preview of the file
    """
    path = Path(file_path)
    if not path.exists():
        return f"[File not found: {path.name}]"

    ext = path.suffix.lower()
    filename = path.name
    file_size = path.stat().st_size

    try:
        if ext in (".xlsx", ".xls"):
            return _preview_excel(path, filename, file_size, max_rows, max_chars)
        elif ext == ".csv":
            return _preview_csv(path, filename, file_size, max_rows, max_chars)
        elif ext == ".docx":
            return _preview_docx(path, filename, file_size, max_chars)
        elif ext == ".pdf":
            return _preview_pdf(path, filename, file_size, max_chars)
        elif ext in (".txt", ".md", ".json", ".html", ".xml", ".yaml", ".yml"):
            return _preview_text(path, filename, file_size, max_chars)
        elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
            return _preview_image(path, filename, file_size)
        else:
            return (
                f"📎 {filename} ({_fmt_size(file_size)})\n"
                f"  Type: {ext} — preview not supported, file is copied to working directory"
            )
    except Exception as e:
        return f"📎 {filename} ({_fmt_size(file_size)})\n  ⚠️ Preview error: {str(e)}"


def generate_all_previews(
    file_paths: List[str],
    max_rows: int = MAX_PREVIEW_ROWS,
    max_chars: int = MAX_PREVIEW_CHARS_PER_FILE,
    max_total_chars: int = MAX_TOTAL_PREVIEW_CHARS,
) -> Optional[str]:
    """
    Generate combined previews for all reference files.

    Args:
        file_paths: List of absolute file paths
        max_rows: Max rows per tabular file
        max_chars: Max characters per file preview
        max_total_chars: Max total characters for all previews combined

    Returns:
        Combined preview string, or None if no files
    """
    if not file_paths:
        return None

    previews = []
    total_chars = 0

    for fp in file_paths:
        preview = generate_file_preview(fp, max_rows, max_chars)
        if total_chars + len(preview) > max_total_chars:
            remaining = max_total_chars - total_chars
            if remaining > 100:
                preview = preview[:remaining] + "\n  ... (truncated)"
            else:
                previews.append(f"  ... ({len(file_paths) - len(previews)} more files, truncated)")
                break
        previews.append(preview)
        total_chars += len(preview)

    header = (
        "═══ REFERENCE FILES PREVIEW ═══\n"
        "The following reference files are available in the current directory.\n"
        "Use EXACT column names, sheet names, and data values shown below.\n"
    )
    return header + "\n\n" + "\n\n".join(previews) + "\n═══ END REFERENCE FILES ═══"


# ─── Format helpers ───


def _fmt_size(size_bytes: int) -> str:
    """Format file size as human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


# ─── Format-specific preview generators ───


def _preview_excel(
    path: Path, filename: str, file_size: int, max_rows: int, max_chars: int
) -> str:
    """Preview Excel file: sheet names, columns, first N rows."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    lines = [f"📊 {filename} ({_fmt_size(file_size)})"]

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))

        if not rows:
            lines.append(f"  Sheet: {sheet_name} — (empty)")
            continue

        # First row as headers
        headers = [str(h) if h is not None else "" for h in rows[0]]
        data_rows = rows[1:]
        total_rows = len(data_rows)

        lines.append(f"  Sheet: {sheet_name} ({total_rows} rows × {len(headers)} cols)")
        lines.append(f"  Columns: {', '.join(headers)}")

        # Show first N data rows
        show_rows = data_rows[:max_rows]
        if show_rows:
            lines.append(f"  First {len(show_rows)} rows:")
            for i, row in enumerate(show_rows):
                row_str = " | ".join(
                    str(cell) if cell is not None else "" for cell in row
                )
                lines.append(f"    [{i+1}] {row_str}")

        if total_rows > max_rows:
            lines.append(f"    ... ({total_rows - max_rows} more rows)")

    wb.close()
    result = "\n".join(lines)
    return result[:max_chars] if len(result) > max_chars else result


def _preview_csv(
    path: Path, filename: str, file_size: int, max_rows: int, max_chars: int
) -> str:
    """Preview CSV file: columns, first N rows."""
    import csv

    lines = [f"📊 {filename} ({_fmt_size(file_size)})"]

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        rows = []
        for i, row in enumerate(reader):
            rows.append(row)
            if i >= max_rows + 1:  # +1 for header
                break

    if not rows:
        lines.append("  (empty file)")
        return "\n".join(lines)

    headers = rows[0]
    data_rows = rows[1:]

    lines.append(f"  Columns: {', '.join(headers)}")
    lines.append(f"  First {len(data_rows)} rows:")
    for i, row in enumerate(data_rows):
        row_str = " | ".join(row)
        lines.append(f"    [{i+1}] {row_str}")

    result = "\n".join(lines)
    return result[:max_chars] if len(result) > max_chars else result


def _preview_docx(path: Path, filename: str, file_size: int, max_chars: int) -> str:
    """Preview Word document: extract text content."""
    from docx import Document

    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

    lines = [f"📝 {filename} ({_fmt_size(file_size)}, {len(paragraphs)} paragraphs)"]

    text = "\n".join(paragraphs)
    if len(text) > max_chars - 200:
        text = text[: max_chars - 200] + "\n  ... (truncated)"

    lines.append(text)

    return "\n".join(lines)


def _preview_pdf(path: Path, filename: str, file_size: int, max_chars: int) -> str:
    """Preview PDF: extract text via pdfplumber."""
    import pdfplumber

    lines = [f"📄 {filename} ({_fmt_size(file_size)})"]

    with pdfplumber.open(path) as pdf:
        num_pages = len(pdf.pages)
        lines.append(f"  Pages: {num_pages}")

        text_parts = []
        for page in pdf.pages[:5]:  # First 5 pages max
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        text = "\n".join(text_parts)
        if len(text) > max_chars - 200:
            text = text[: max_chars - 200] + "\n  ... (truncated)"

        if text.strip():
            lines.append(text)
        else:
            lines.append("  (no extractable text — may be image-based PDF)")

    return "\n".join(lines)


def _preview_text(path: Path, filename: str, file_size: int, max_chars: int) -> str:
    """Preview text-based file."""
    lines = [f"📝 {filename} ({_fmt_size(file_size)})"]

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_chars - 100:
            content = content[: max_chars - 100] + "\n  ... (truncated)"
        lines.append(content)
    except Exception as e:
        lines.append(f"  ⚠️ Read error: {e}")

    return "\n".join(lines)


def _preview_image(path: Path, filename: str, file_size: int) -> str:
    """Preview image: dimensions and file size only."""
    info = f"🖼️ {filename} ({_fmt_size(file_size)})"

    try:
        from PIL import Image

        with Image.open(path) as img:
            w, h = img.size
            info += f"\n  Dimensions: {w}×{h}px, Mode: {img.mode}"
    except Exception:
        info += "\n  (could not read image dimensions)"

    return info
