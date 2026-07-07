---
name: document
title: Document Reading & Authoring
description: >-
  Read and author office documents. Use for any task with document reference
  files (.pdf/.docx/.pptx/.xlsx/.csv) or that asks to produce reports,
  contracts, decks, spreadsheets, or memos. Extracts text and tables, renders
  PDF pages to images for visual inspection, and provides thin builders for
  DOCX/PDF/PPTX/XLSX deliverables.
modalities: [document]
file_extensions:
  [".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".rtf", ".odt"]
keywords:
  [document, report, memo, contract, brief, letter, deck, slide, presentation,
   spreadsheet, workbook, table, pdf, docx, pptx, xlsx, invoice, statement,
   form, page, paragraph, heading]
requires: [pdfplumber, PyMuPDF, python-docx, python-pptx, openpyxl, pandas]
version: 1.0.0
---

# Document Skill — read & write office files

Use this skill to *read* reference documents accurately (exact text, tables,
and — via page images — layout) and to *author* polished deliverables.

A typical "document problem" workflow:

1. `text = document.read_any(path)` — extract text from PDF/DOCX/PPTX/XLSX/CSV.
2. `tables = document.pdf_tables(path)` — pull tabular data from PDFs.
3. (visual check) `imgs = document.pdf_to_images(path)` — render pages to PNG so
   the vision layer / `image` skill can inspect layout, charts, signatures.
4. Build the deliverable with the appropriate builder.

## Toolkit API

```python
from skills import document

document.read_any(path) -> str            # auto-dispatch by extension
document.read_pdf_text(path) -> str       # pdfplumber text
document.pdf_tables(path) -> list[list[list]]   # tables per page
document.pdf_to_images(path, out_dir="pages", dpi=150) -> list[str]  # PyMuPDF
document.read_docx(path) -> str
document.read_pptx(path) -> list[str]     # text per slide
document.read_xlsx(path) -> dict          # {sheet: [rows...]}

document.make_docx(title, paragraphs, out) -> str
document.make_pdf(title, lines, out) -> str
document.make_pptx(title, slides, out) -> str   # slides = [(heading, [bullets])]
document.make_xlsx(sheets, out) -> str          # sheets = {name: [rows...]}
```

Notes:
- `pdf_to_images` is the bridge to *vision*: render pages, then inspect them with
  the `image` skill (OCR / colours) or describe them.
- Builders are intentionally thin — for rich formatting use python-docx /
  python-pptx / reportlab / openpyxl directly (all pre-installed).
