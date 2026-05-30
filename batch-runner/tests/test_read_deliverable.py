"""Tests for ``core.tools.read_deliverable`` (PR2 task 201)."""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path

import pytest

from core.tools import (
    READ_DELIVERABLE_OPS,
    READ_DELIVERABLE_TOOL_SCHEMA,
    read_deliverable,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def xlsx_file(base_dir: Path) -> Path:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Item"
    ws["B1"] = "Value"
    ws["A2"] = "alpha"
    ws["B2"] = 1
    ws["A3"] = "beta"
    ws["B3"] = 2
    # Add a bit of formatting so inspect_formatting has something to see.
    from openpyxl.styles import Font, PatternFill, Border, Side
    ws["A1"].font = Font(bold=True)
    ws["A1"].fill = PatternFill("solid", fgColor="FFFF00")
    ws["A1"].border = Border(bottom=Side(style="thin"))
    ws.merge_cells("A1:B1")
    p = base_dir / "report.xlsx"
    wb.save(p)
    return p


@pytest.fixture
def docx_file(base_dir: Path) -> Path:
    pytest.importorskip("docx")
    from docx import Document
    doc = Document()
    doc.add_heading("Title", level=1)
    doc.add_paragraph("First paragraph body.")
    doc.add_paragraph("Second paragraph body.")
    p = base_dir / "memo.docx"
    doc.save(p)
    return p


@pytest.fixture
def pdf_file(base_dir: Path) -> Path:
    """Generate a tiny 1-page PDF via reportlab (already in requirements)."""
    reportlab = pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas
    p = base_dir / "doc.pdf"
    c = canvas.Canvas(str(p))
    c.drawString(100, 750, "Hello PDF world.")
    c.showPage()
    c.save()
    return p


@pytest.fixture
def png_file(base_dir: Path) -> Path:
    pytest.importorskip("PIL")
    from PIL import Image
    p = base_dir / "img.png"
    Image.new("RGB", (16, 16), color="red").save(p)
    return p


@pytest.fixture
def txt_file(base_dir: Path) -> Path:
    p = base_dir / "notes.txt"
    p.write_text("hello world\nline 2\n", encoding="utf-8")
    return p


# ── Schema / surface ─────────────────────────────────────────────────


def test_ops_constant_matches_schema_enum():
    enum = READ_DELIVERABLE_TOOL_SCHEMA["parameters"]["properties"]["op"]["enum"]
    assert tuple(enum) == READ_DELIVERABLE_OPS
    assert len(READ_DELIVERABLE_OPS) == 6


# ── Path safety ──────────────────────────────────────────────────────


def test_rejects_traversal_outside_base(base_dir, txt_file):
    # Create a sibling outside the base
    outside = base_dir.parent / "secret.txt"
    outside.write_text("nope")
    result = read_deliverable(
        "read_content",
        f"../{outside.name}",
        base_dir=str(base_dir),
    )
    assert result["ok"] is False
    assert result["error_type"] == "bad_path"


def test_rejects_absolute_outside_base(base_dir):
    result = read_deliverable(
        "read_content",
        "/etc/passwd",
        base_dir=str(base_dir),
    )
    assert result["ok"] is False
    assert result["error_type"] == "bad_path"


def test_rejects_missing_file(base_dir):
    result = read_deliverable(
        "read_content",
        "no_such_file.txt",
        base_dir=str(base_dir),
    )
    assert result["ok"] is False
    assert result["error_type"] == "bad_path"


def test_rejects_unknown_op(base_dir, txt_file):
    result = read_deliverable(
        "rm_rf",
        txt_file.name,
        base_dir=str(base_dir),
    )
    assert result["ok"] is False
    assert result["error_type"] == "bad_op"


# ── inspect_structure ────────────────────────────────────────────────


def test_inspect_structure_txt(base_dir, txt_file):
    r = read_deliverable("inspect_structure", txt_file.name, base_dir=str(base_dir))
    assert r["ok"] is True
    assert r["data"]["kind"] == "txt"
    assert r["data"]["size_bytes"] > 0


def test_inspect_structure_xlsx(base_dir, xlsx_file):
    r = read_deliverable("inspect_structure", xlsx_file.name, base_dir=str(base_dir))
    assert r["ok"] is True
    d = r["data"]
    assert d["kind"] == "xlsx"
    assert d["sheet_count"] == 1
    assert d["sheets"][0]["name"] == "Summary"


def test_inspect_structure_docx(base_dir, docx_file):
    r = read_deliverable("inspect_structure", docx_file.name, base_dir=str(base_dir))
    assert r["ok"] is True
    assert r["data"]["kind"] == "docx"
    assert r["data"]["paragraph_count"] >= 2


def test_inspect_structure_pdf(base_dir, pdf_file):
    r = read_deliverable("inspect_structure", pdf_file.name, base_dir=str(base_dir))
    assert r["ok"] is True
    assert r["data"]["kind"] == "pdf"
    assert r["data"]["page_count"] == 1


# ── read_content ─────────────────────────────────────────────────────


def test_read_content_txt(base_dir, txt_file):
    r = read_deliverable("read_content", txt_file.name, base_dir=str(base_dir))
    assert r["ok"] is True
    assert "hello world" in r["data"]["text"]


def test_read_content_xlsx_full(base_dir, xlsx_file):
    r = read_deliverable("read_content", xlsx_file.name, base_dir=str(base_dir))
    assert r["ok"] is True
    assert "alpha" in r["data"]["text"]
    assert "beta" in r["data"]["text"]


def test_read_content_xlsx_scope_sheet(base_dir, xlsx_file):
    r = read_deliverable(
        "read_content",
        xlsx_file.name,
        base_dir=str(base_dir),
        scope={"sheet": "Summary"},
    )
    assert r["ok"] is True
    assert "Summary" in r["data"]["text"]


def test_read_content_pdf(base_dir, pdf_file):
    r = read_deliverable("read_content", pdf_file.name, base_dir=str(base_dir))
    assert r["ok"] is True
    assert "Hello PDF" in r["data"]["text"]


def test_read_content_docx(base_dir, docx_file):
    r = read_deliverable("read_content", docx_file.name, base_dir=str(base_dir))
    assert r["ok"] is True
    assert "First paragraph" in r["data"]["text"]


def test_read_content_truncation_flag(base_dir):
    big = base_dir / "big.txt"
    big.write_text("x" * (300_000))
    r = read_deliverable("read_content", big.name, base_dir=str(base_dir))
    assert r["ok"] is True
    assert r["data"]["truncated"] is True
    assert r["data"]["char_count"] <= 200_000


# ── inspect_formatting ───────────────────────────────────────────────


def test_inspect_formatting_xlsx(base_dir, xlsx_file):
    r = read_deliverable("inspect_formatting", xlsx_file.name, base_dir=str(base_dir))
    assert r["ok"] is True
    d = r["data"]
    sheet = d["sheets"][0]
    assert sheet["merged_ranges"]
    assert sheet["styled_cells_count"] >= 1


def test_inspect_formatting_docx(base_dir, docx_file):
    r = read_deliverable("inspect_formatting", docx_file.name, base_dir=str(base_dir))
    assert r["ok"] is True
    assert r["data"]["kind"] == "docx"
    assert "style_histogram" in r["data"]


# ── render_to_image ──────────────────────────────────────────────────


def test_render_to_image_pdf(base_dir, pdf_file):
    pytest.importorskip("fitz")
    r = read_deliverable(
        "render_to_image", pdf_file.name,
        base_dir=str(base_dir), scope={"page": 1},
    )
    assert r["ok"] is True
    payload = r["data"]
    assert payload["kind"] == "image_png_base64"
    raw = base64.b64decode(payload["base64"])
    assert raw.startswith(b"\x89PNG")
    assert payload["byte_size"] <= 5 * 1024 * 1024


def test_render_to_image_png(base_dir, png_file):
    r = read_deliverable(
        "render_to_image", png_file.name,
        base_dir=str(base_dir),
    )
    assert r["ok"] is True
    raw = base64.b64decode(r["data"]["base64"])
    assert raw.startswith(b"\x89PNG")


def test_render_to_image_rejects_xlsx(base_dir, xlsx_file):
    r = read_deliverable(
        "render_to_image", xlsx_file.name,
        base_dir=str(base_dir), scope={"sheet": "Summary"},
    )
    assert r["ok"] is False
    assert r["error_type"] == "op_error"


def test_render_pdf_out_of_range(base_dir, pdf_file):
    pytest.importorskip("fitz")
    r = read_deliverable(
        "render_to_image", pdf_file.name,
        base_dir=str(base_dir), scope={"page": 99},
    )
    assert r["ok"] is False


# ── render_to_image size cap (downsample) ────────────────────────────


def test_render_to_image_size_cap(base_dir):
    PIL = pytest.importorskip("PIL")
    from PIL import Image
    # Generate a noisy PNG that exceeds the 5MB cap pre-downsample.
    big = base_dir / "big.png"
    import os as _os
    img = Image.effect_noise((3000, 3000), 64)
    img = img.convert("RGB")
    img.save(big, format="PNG")
    if _os.path.getsize(big) < 5 * 1024 * 1024:
        pytest.skip("noise PNG fortuitously small; cap path not exercised")
    r = read_deliverable("render_to_image", big.name, base_dir=str(base_dir))
    assert r["ok"] is True
    assert r["data"]["byte_size"] <= 5 * 1024 * 1024


# ── probe_audio / probe_video ────────────────────────────────────────


def test_probe_audio_wav(base_dir):
    pytest.importorskip("av")
    import wave
    import struct
    p = base_dir / "tone.wav"
    framerate = 8000
    duration_s = 1
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        # ~440Hz square-ish wave so silence_ratio < 1
        samples = bytes()
        import math
        for i in range(framerate * duration_s):
            val = int(10000 * (1 if (i // 9) % 2 else -1))
            samples += struct.pack("<h", val)
        w.writeframes(samples)
    r = read_deliverable("probe_audio", p.name, base_dir=str(base_dir))
    assert r["ok"] is True
    data = r["data"]
    assert data["sample_rate"] == framerate
    assert data["channels"] == 1
    assert data["duration_s"] is not None
    assert 0.5 < data["duration_s"] < 1.5
    assert "peak_amplitude_normalized" in data


def test_probe_audio_rejects_non_audio(base_dir, txt_file):
    r = read_deliverable("probe_audio", txt_file.name, base_dir=str(base_dir))
    assert r["ok"] is True  # graceful, but note
    assert "note" in r["data"]


def test_probe_video_note_for_non_video(base_dir, txt_file):
    r = read_deliverable("probe_video", txt_file.name, base_dir=str(base_dir))
    assert r["ok"] is True
    assert "note" in r["data"]
