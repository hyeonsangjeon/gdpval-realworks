"""Tests for ``core.tools.read_deliverable`` (PR2 task 201)."""

from __future__ import annotations

import base64
import importlib
import io
import os
from pathlib import Path

import pytest

from core.tools import (
    get_renderer_fingerprint,
    MODEL_READ_DELIVERABLE_OPS,
    MODEL_READ_DELIVERABLE_TOOL_SCHEMA,
    READ_DELIVERABLE_OPS,
    READ_DELIVERABLE_TOOL_SCHEMA,
    RendererDependencyError,
    read_deliverable,
)

read_deliverable_module = importlib.import_module("core.tools.read_deliverable")


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
def pptx_file(base_dir: Path) -> Path:
    pytest.importorskip("pptx")
    from pptx import Presentation

    presentation = Presentation()
    for title in ("Overview", "Details"):
        slide = presentation.slides.add_slide(presentation.slide_layouts[5])
        slide.shapes.title.text = title
    p = base_dir / "slides.pptx"
    presentation.save(p)
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


def _fake_convert_to_pdf(source: Path, out_dir: Path, pages: int = 2) -> Path:
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    output = out_dir / f"{source.stem}.pdf"
    document = canvas.Canvas(str(output))
    for page in range(1, pages + 1):
        document.drawString(100, 750, f"Rendered page {page}")
        document.showPage()
    document.save()
    return output


# ── Schema / surface ─────────────────────────────────────────────────


def test_ops_constant_matches_schema_enum():
    enum = READ_DELIVERABLE_TOOL_SCHEMA["parameters"]["properties"]["op"]["enum"]
    assert tuple(enum) == READ_DELIVERABLE_OPS
    assert len(READ_DELIVERABLE_OPS) == 6


def test_model_schema_excludes_harness_only_render_op():
    enum = MODEL_READ_DELIVERABLE_TOOL_SCHEMA[
        "parameters"
    ]["properties"]["op"]["enum"]
    assert tuple(enum) == MODEL_READ_DELIVERABLE_OPS
    assert "render_to_image" in READ_DELIVERABLE_OPS
    assert "render_to_image" not in MODEL_READ_DELIVERABLE_OPS
    assert "base64" not in str(MODEL_READ_DELIVERABLE_TOOL_SCHEMA).lower()


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


def test_inspect_formatting_xlsx_preserves_color_types_without_descriptor_junk(
    base_dir,
):
    openpyxl = pytest.importorskip("openpyxl")
    from openpyxl.styles import Color, Font, PatternFill

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    colors = {
        "A1": (Color(rgb="FF112233"), Color(rgb="FF445566")),
        "A2": (Color(theme=4, tint=0.4), Color(theme=5, tint=-0.25)),
        "A3": (Color(indexed=7), Color(indexed=8)),
        "A4": (Color(auto=True), Color(auto=True)),
    }
    for ref, (font_color, fill_color) in colors.items():
        sheet[ref] = ref
        sheet[ref].font = Font(color=font_color)
        sheet[ref].fill = PatternFill(fill_type="solid", fgColor=fill_color)
    sheet["A5"] = "plain"
    sheet["A6"] = 1
    sheet["A6"].number_format = "0.00"

    path = base_dir / "colors.xlsx"
    workbook.save(path)

    result = read_deliverable("inspect_formatting", path.name, base_dir=str(base_dir))

    assert result["ok"] is True
    styled = {
        cell["ref"]: cell
        for cell in result["data"]["sheets"][0]["styled_cells_sample"]
    }
    assert styled["A1"]["font_color"] == "FF112233"
    assert styled["A1"]["fill"] == "FF445566"
    assert styled["A2"]["font_color"] == "theme:4:tint:0.4"
    assert styled["A2"]["fill"] == "theme:5:tint:-0.25"
    assert styled["A3"]["font_color"] == "indexed:7"
    assert styled["A3"]["fill"] == "indexed:8"
    assert styled["A4"]["font_color"] == "auto"
    assert styled["A4"]["fill"] == "auto"
    assert set(styled) == set(colors)
    assert result["data"]["sheets"][0]["styled_cells_count"] == len(colors)
    assert "Values must be of type" not in str(result)


def test_default_font_color_lookup_fails_soft_when_openpyxl_internals_change():
    class WorkbookWithoutStyleInternals:
        pass

    class CellWithoutStyleInternals:
        font = type("Font", (), {"color": "explicit"})()

    assert (
        read_deliverable_module._workbook_default_font_color(
            WorkbookWithoutStyleInternals()
        )
        is None
    )
    assert (
        read_deliverable_module._nondefault_font_color(
            CellWithoutStyleInternals(), None
        )
        is None
    )


def test_inspect_formatting_docx(base_dir, docx_file):
    r = read_deliverable("inspect_formatting", docx_file.name, base_dir=str(base_dir))
    assert r["ok"] is True
    assert r["data"]["kind"] == "docx"
    assert "style_histogram" in r["data"]


# ── render_to_image ──────────────────────────────────────────────────


def test_render_to_image_pdf(base_dir, pdf_file, monkeypatch):
    pytest.importorskip("fitz")
    monkeypatch.setattr(
        read_deliverable_module, "_pymupdf_runtime_version", lambda: "9.9.9"
    )
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
    assert payload["scope"] == {"page": 1}
    assert payload["source_page_count"] == 1
    assert payload["renderer"]["pymupdf_version"] == "9.9.9"


def test_render_to_image_png(base_dir, png_file):
    r = read_deliverable(
        "render_to_image", png_file.name,
        base_dir=str(base_dir),
    )
    assert r["ok"] is True
    raw = base64.b64decode(r["data"]["base64"])
    assert raw.startswith(b"\x89PNG")


def test_render_to_image_xlsx_uses_original_path_and_is_read_only(
    base_dir, xlsx_file, monkeypatch
):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.load_workbook(xlsx_file)
    workbook.create_sheet("Details")["A1"] = "second sheet"
    workbook.save(xlsx_file)
    workbook.close()
    source_before = xlsx_file.read_bytes()
    observed = {}

    def fake_convert(source: Path, out_dir: Path) -> Path:
        observed["source"] = source
        observed["bytes"] = source.read_bytes()
        return _fake_convert_to_pdf(source, out_dir, pages=2)

    monkeypatch.setattr(
        read_deliverable_module, "_convert_office_to_pdf", fake_convert
    )
    monkeypatch.setattr(
        read_deliverable_module,
        "get_renderer_fingerprint",
        lambda: {
            "libreoffice_binary": "soffice",
            "libreoffice_version": "LibreOffice 24.2.7.2",
            "pymupdf_version": "1.26.3",
        },
    )
    r = read_deliverable(
        "render_to_image", xlsx_file.name,
        base_dir=str(base_dir), scope={"workbook_page": 1},
    )
    assert r["ok"] is True
    payload = r["data"]
    assert payload["source_kind"] == "xlsx"
    assert payload["scope"] == {"workbook_page": 1}
    assert payload["source_sheet_count"] == 2
    assert payload["converted_page_count"] == 2
    assert payload["renderer"]["converter"] == "libreoffice"
    assert payload["renderer"]["libreoffice_binary"] == "soffice"
    assert payload["renderer"]["libreoffice_version"] == "LibreOffice 24.2.7.2"
    assert payload["renderer"]["pymupdf_version"] == "1.26.3"
    assert "/usr/" not in str(payload["renderer"])
    assert base64.b64decode(payload["base64"]).startswith(b"\x89PNG")
    assert observed["source"] == xlsx_file
    assert observed["bytes"] == source_before
    assert xlsx_file.read_bytes() == source_before


def test_render_to_image_pptx_selected_slide(
    base_dir, pptx_file, monkeypatch
):
    monkeypatch.setattr(
        read_deliverable_module, "_convert_office_to_pdf", _fake_convert_to_pdf
    )
    monkeypatch.setattr(
        read_deliverable_module,
        "get_renderer_fingerprint",
        lambda: {
            "libreoffice_binary": "libreoffice",
            "libreoffice_version": "LibreOffice 24.2.7.2",
            "pymupdf_version": "1.26.3",
        },
    )
    r = read_deliverable(
        "render_to_image", pptx_file.name,
        base_dir=str(base_dir), scope={"slide": 2},
    )
    assert r["ok"] is True
    payload = r["data"]
    assert payload["source_kind"] == "pptx"
    assert payload["scope"] == {"slide": 2}
    assert payload["source_slide_count"] == 2
    assert payload["converted_page_count"] == 2
    assert payload["renderer"]["libreoffice_binary"] == "libreoffice"
    assert payload["renderer"]["libreoffice_version"] == "LibreOffice 24.2.7.2"
    assert payload["renderer"]["pymupdf_version"] == "1.26.3"
    assert base64.b64decode(payload["base64"]).startswith(b"\x89PNG")


def test_render_xlsx_missing_libreoffice_is_actionable(
    base_dir, xlsx_file, monkeypatch
):
    monkeypatch.setattr(read_deliverable_module, "_find_soffice", lambda: None)
    r = read_deliverable(
        "render_to_image", xlsx_file.name,
        base_dir=str(base_dir), scope={"workbook_page": 1},
    )
    assert r["ok"] is False
    assert r["error_type"] == "dependency_missing"
    assert "LibreOffice" in r["error"]
    assert "install" in r["error"].lower()


def test_render_pdf_out_of_range(base_dir, pdf_file):
    pytest.importorskip("fitz")
    r = read_deliverable(
        "render_to_image", pdf_file.name,
        base_dir=str(base_dir), scope={"page": 99},
    )
    assert r["ok"] is False
    assert r["error_type"] == "bad_scope"
    assert "out of range" in r["error"]


@pytest.mark.parametrize("page", [0, -1, 1.5, True, "first"])
def test_render_pdf_rejects_invalid_page_scope(base_dir, pdf_file, page):
    r = read_deliverable(
        "render_to_image", pdf_file.name,
        base_dir=str(base_dir), scope={"page": page},
    )
    assert r["ok"] is False
    assert r["error_type"] == "bad_scope"
    assert "positive 1-based integer" in r["error"]


@pytest.mark.parametrize("legacy_scope", [{"sheet": "Summary"}, {"sheet_page": 1}])
def test_render_xlsx_rejects_named_sheet_scope(
    base_dir, xlsx_file, monkeypatch, legacy_scope
):
    monkeypatch.setattr(
        read_deliverable_module,
        "_convert_office_to_pdf",
        lambda *_: pytest.fail("conversion must not run for an invalid sheet"),
    )
    r = read_deliverable(
        "render_to_image", xlsx_file.name,
        base_dir=str(base_dir), scope=legacy_scope,
    )
    assert r["ok"] is False
    assert r["error_type"] == "unsupported_scope"
    assert "workbook_page" in r["error"]


def test_render_xlsx_unknown_key_beats_legacy_scope(
    base_dir, xlsx_file, monkeypatch
):
    monkeypatch.setattr(
        read_deliverable_module,
        "_convert_office_to_pdf",
        lambda *_: pytest.fail("conversion must not run for invalid scope"),
    )
    result = read_deliverable(
        "render_to_image", xlsx_file.name, base_dir=str(base_dir),
        scope={"sheet": "Summary", "bogus": 1},
    )
    assert result["ok"] is False
    assert result["error_type"] == "bad_scope"
    assert "bogus" in result["error"]


def test_render_xlsx_rejects_workbook_page_after_first(
    base_dir, xlsx_file, monkeypatch
):
    monkeypatch.setattr(
        read_deliverable_module,
        "_convert_office_to_pdf",
        lambda *_: pytest.fail("conversion must not run for unsupported page"),
    )
    r = read_deliverable(
        "render_to_image", xlsx_file.name,
        base_dir=str(base_dir), scope={"workbook_page": 2},
    )
    assert r["ok"] is False
    assert r["error_type"] == "unsupported_scope"
    assert "only workbook_page=1" in r["error"]


def test_render_pptx_rejects_out_of_range_slide(
    base_dir, pptx_file, monkeypatch
):
    monkeypatch.setattr(
        read_deliverable_module,
        "_convert_office_to_pdf",
        lambda *_: pytest.fail("conversion must not run for an invalid slide"),
    )
    r = read_deliverable(
        "render_to_image", pptx_file.name,
        base_dir=str(base_dir), scope={"slide": 3},
    )
    assert r["ok"] is False
    assert r["error_type"] == "bad_scope"
    assert "out of range" in r["error"]


@pytest.mark.parametrize(
    "fixture_name,scope",
    [
        ("pdf_file", {"slide": 1}),
        ("pptx_file", {"page": 1}),
        ("xlsx_file", {"page": 1}),
        ("png_file", {"page": 1}),
    ],
)
def test_render_rejects_unknown_scope_keys(
    request, base_dir, fixture_name, scope
):
    path = request.getfixturevalue(fixture_name)
    r = read_deliverable(
        "render_to_image", path.name, base_dir=str(base_dir), scope=scope,
    )
    assert r["ok"] is False
    assert r["error_type"] == "bad_scope"
    assert "unknown scope keys" in r["error"]


def test_render_rejects_non_object_scope(base_dir, pdf_file):
    r = read_deliverable(
        "render_to_image", pdf_file.name,
        base_dir=str(base_dir), scope=[1],  # type: ignore[arg-type]
    )
    assert r["ok"] is False
    assert r["error_type"] == "bad_scope"


def test_render_to_image_still_rejects_unsupported_text(base_dir, txt_file):
    r = read_deliverable(
        "render_to_image", txt_file.name, base_dir=str(base_dir),
    )
    assert r["ok"] is False
    assert r["error_type"] == "unsupported_scope"
    assert "not supported for kind=txt" in r["error"]


def test_render_to_image_still_rejects_docx(base_dir, docx_file):
    r = read_deliverable(
        "render_to_image", docx_file.name, base_dir=str(base_dir),
    )
    assert r["ok"] is False
    assert r["error_type"] == "unsupported_scope"
    assert "not supported for kind=docx" in r["error"]


def test_libreoffice_conversion_uses_isolated_profile_and_allowlisted_env(
    base_dir, xlsx_file, monkeypatch
):
    observed = {}
    monkeypatch.setattr(
        read_deliverable_module, "_find_soffice", lambda: "/usr/bin/soffice"
    )
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("SECRET_TOKEN", "must-not-leak")

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["env"] = kwargs["env"]
        output = Path(command[command.index("--outdir") + 1]) / "report.pdf"
        output.write_bytes(b"%PDF-fake")
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(read_deliverable_module.subprocess, "run", fake_run)
    with read_deliverable_module.tempfile.TemporaryDirectory() as temp:
        read_deliverable_module._convert_office_to_pdf(xlsx_file, Path(temp))

    command = observed["command"]
    assert "--headless" in command
    assert "--safe-mode" in command
    assert "--norestore" in command
    assert any(arg.startswith("-env:UserInstallation=file:") for arg in command)
    assert all(
        key in {"PATH", "HOME", "TMPDIR", "LANG"} or key.startswith("LC_")
        for key in observed["env"]
    )
    assert "AZURE_OPENAI_API_KEY" not in observed["env"]
    assert "SECRET_TOKEN" not in observed["env"]


def test_renderer_fingerprint_is_cached_by_selected_executable_and_isolated(
    monkeypatch,
):
    observed = []
    read_deliverable_module._renderer_fingerprint_for_executable.cache_clear()
    monkeypatch.setattr(
        read_deliverable_module,
        "_find_soffice",
        lambda: "/opt/libreoffice/program/soffice",
    )
    monkeypatch.setattr(
        read_deliverable_module, "_pymupdf_runtime_version", lambda: "1.26.3"
    )
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("SECRET_TOKEN", "must-not-leak")

    def fake_run(command, **kwargs):
        observed.append((command, kwargs))
        return type(
            "Completed",
            (),
            {
                "returncode": 0,
                "stdout": "LibreOffice 24.2.7.2 build:abc\nextra\n",
                "stderr": "",
            },
        )()

    monkeypatch.setattr(read_deliverable_module.subprocess, "run", fake_run)

    first = get_renderer_fingerprint()
    second = get_renderer_fingerprint()

    assert first == second == {
        "libreoffice_binary": "soffice",
        "libreoffice_version": "LibreOffice 24.2.7.2 build:abc",
        "pymupdf_version": "1.26.3",
    }
    assert len(observed) == 1
    command, kwargs = observed[0]
    assert command == [
        "/opt/libreoffice/program/soffice", "--headless", "--version"
    ]
    assert kwargs["shell"] is False
    assert kwargs["check"] is False
    assert kwargs["timeout"] <= 10
    assert kwargs["env"]["HOME"] == kwargs["env"]["TMPDIR"]
    assert all(
        key in {"PATH", "HOME", "TMPDIR", "LANG"} or key.startswith("LC_")
        for key in kwargs["env"]
    )
    assert "AZURE_OPENAI_API_KEY" not in kwargs["env"]
    assert "SECRET_TOKEN" not in kwargs["env"]
    assert all("/opt/libreoffice" not in value for value in first.values())


def test_renderer_fingerprint_fails_closed_when_libreoffice_missing(monkeypatch):
    read_deliverable_module._renderer_fingerprint_for_executable.cache_clear()
    monkeypatch.setattr(read_deliverable_module, "_find_soffice", lambda: None)

    with pytest.raises(RendererDependencyError, match="LibreOffice executable"):
        get_renderer_fingerprint()


def test_renderer_fingerprint_fails_closed_on_bad_version_probe(monkeypatch):
    read_deliverable_module._renderer_fingerprint_for_executable.cache_clear()
    monkeypatch.setattr(
        read_deliverable_module, "_find_soffice", lambda: "/usr/bin/soffice"
    )
    monkeypatch.setattr(
        read_deliverable_module.subprocess,
        "run",
        lambda *args, **kwargs: type(
            "Completed",
            (),
            {"returncode": 1, "stdout": "", "stderr": "probe failed"},
        )(),
    )

    with pytest.raises(RendererDependencyError, match="exit 1"):
        get_renderer_fingerprint()


def test_renderer_fingerprint_bounds_version_to_first_line(monkeypatch):
    read_deliverable_module._renderer_fingerprint_for_executable.cache_clear()
    monkeypatch.setattr(
        read_deliverable_module, "_find_soffice", lambda: "/usr/bin/soffice"
    )
    monkeypatch.setattr(
        read_deliverable_module, "_pymupdf_runtime_version", lambda: "1.26.3"
    )
    monkeypatch.setattr(
        read_deliverable_module.subprocess,
        "run",
        lambda *args, **kwargs: type(
            "Completed",
            (),
            {
                "returncode": 0,
                "stdout": ("L" * 500) + "\nsecond line must not appear",
                "stderr": "",
            },
        )(),
    )

    fingerprint = get_renderer_fingerprint()

    assert fingerprint["libreoffice_version"] == "L" * 200
    assert "second line" not in fingerprint["libreoffice_version"]


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
