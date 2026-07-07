"""Document skill — re-exports the toolkit helpers."""

from skills.document.toolkit import (  # noqa: F401
    make_docx,
    make_pdf,
    make_pptx,
    make_xlsx,
    pdf_tables,
    pdf_to_images,
    read_any,
    read_docx,
    read_pdf_text,
    read_pptx,
    read_xlsx,
)

__all__ = [
    "make_docx",
    "make_pdf",
    "make_pptx",
    "make_xlsx",
    "pdf_tables",
    "pdf_to_images",
    "read_any",
    "read_docx",
    "read_pdf_text",
    "read_pptx",
    "read_xlsx",
]
