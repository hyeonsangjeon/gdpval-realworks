"""Tests for core/artifact_renderer.py + core/output_qa.py.

Render tests require PyMuPDF (skip gracefully otherwise). They never call an LLM:
vision QA is exercised only with a fake client.
"""

from pathlib import Path

import pytest

from core.artifact_renderer import (
    RenderResult,
    _convert_office_to_pdf,
    render_artifact,
)
from core.deliverable_contract import infer_deliverable_contract
from core.output_qa import run_output_qa


def _make_pdf(path, lines):
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for ln in lines:
        page.insert_text((72, y), ln)
        y += 22
    doc.save(str(path))
    doc.close()


def test_render_pdf_first_page(tmp_path):
    pytest.importorskip("fitz")
    pdf = tmp_path / "doc.pdf"
    _make_pdf(pdf, ["Hello report", "Second line of content"])
    out = tmp_path / "render"
    rr = render_artifact(pdf, out, max_pages=3)
    assert rr.page_count == 1
    assert len(rr.rendered_images) == 1
    assert Path(rr.rendered_images[0]).exists()


def test_render_skips_non_renderable(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")
    rr = render_artifact(f, tmp_path / "render")
    assert rr.rendered_images == []
    assert any("not rendered" in w for w in rr.warnings)


def test_office_conversion_retries_profile_restart_code_once(
    tmp_path, monkeypatch
):
    source = tmp_path / "report.xlsx"
    source.write_bytes(b"fixture")
    output = tmp_path / "verify-work" / "render"
    output.mkdir(parents=True)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            return __import__("subprocess").CompletedProcess(
                command, 81, stdout="", stderr=""
            )
        (output / "report.pdf").write_bytes(b"pdf")
        return __import__("subprocess").CompletedProcess(
            command, 0, stdout="", stderr=""
        )

    monkeypatch.setattr(
        "core.artifact_renderer._find_soffice",
        lambda: "/usr/lib/libreoffice/program/soffice.bin",
    )
    monkeypatch.setattr("core.artifact_renderer.subprocess.run", run)
    result = RenderResult(rel_path="report.xlsx", kind="spreadsheet")

    pdf = _convert_office_to_pdf(source, output, result)

    assert pdf == output / "report.pdf"
    assert result.converted_via == "libreoffice"
    assert len(calls) == 2
    assert any(arg.startswith("-env:UserInstallation=file://") for arg in calls[0])


def test_sparse_text_page_not_flagged_blank(tmp_path):
    pytest.importorskip("fitz")
    pdf = tmp_path / "sparse.pdf"
    _make_pdf(pdf, ["Just one short line"])
    c = infer_deliverable_contract("Produce a PDF report", [])
    rep = run_output_qa([pdf], contract=c, config={"enabled": True, "render": True},
                        out_dir=tmp_path / "r", task_text="Produce a PDF report")
    assert rep.ok is True, rep.blocking_errors


def test_truly_blank_page_blocks_primary(tmp_path):
    fitz = pytest.importorskip("fitz")
    pdf = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf))
    doc.close()
    c = infer_deliverable_contract("Produce a PDF report", [])
    rep = run_output_qa([pdf], contract=c, config={"enabled": True, "render": True},
                        out_dir=tmp_path / "r", task_text="Produce a PDF report")
    assert rep.ok is False
    assert any("blank" in e for e in rep.blocking_errors)


def test_primary_image_must_render_successfully(tmp_path):
    image = tmp_path / "broken.png"
    image.write_bytes(b"not-a-png")
    contract = infer_deliverable_contract("Create a PNG image", [])

    report = run_output_qa(
        [image],
        contract=contract,
        config={"enabled": True, "render": True},
        out_dir=tmp_path / "render",
        task_text="Create a PNG image",
    )

    assert report.ok is False
    assert any("render error" in error for error in report.blocking_errors)
    assert any("no rendered image" in error for error in report.blocking_errors)


@pytest.mark.parametrize(
    ("mode", "color"),
    [("RGB", (255, 255, 255)), ("RGBA", (0, 0, 0, 0))],
)
def test_white_or_transparent_primary_image_is_blocked(
    tmp_path, mode, color
):
    image_module = pytest.importorskip("PIL.Image")
    image = tmp_path / "blank.png"
    image_module.new(mode, (64, 64), color).save(image)
    contract = infer_deliverable_contract("Create a PNG image", [])

    report = run_output_qa(
        [image],
        contract=contract,
        config={"enabled": True, "render": True},
        out_dir=tmp_path / "render",
        task_text="Create a PNG image",
    )

    assert report.ok is False
    assert report.render_reports[0]["page_white_fractions"] == [1.0]
    assert report.render_reports[0]["blank_pages"] == [1]
    assert any("appears blank" in error for error in report.blocking_errors)


@pytest.mark.parametrize("kind", ["xlsx", "docx", "pptx"])
def test_primary_office_artifact_renders_at_least_one_page(tmp_path, kind):
    from core.artifact_renderer import libreoffice_available

    if not libreoffice_available():
        pytest.skip("LibreOffice is unavailable")
    path = tmp_path / f"report.{kind}"
    if kind == "xlsx":
        openpyxl = pytest.importorskip("openpyxl")
        workbook = openpyxl.Workbook()
        workbook.active["A1"] = "Professional report"
        workbook.save(path)
    elif kind == "docx":
        docx = pytest.importorskip("docx")
        document = docx.Document()
        document.add_heading("Professional report", level=1)
        document.save(path)
    else:
        pptx = pytest.importorskip("pptx")
        presentation = pptx.Presentation()
        slide = presentation.slides.add_slide(presentation.slide_layouts[0])
        slide.shapes.title.text = "Professional report"
        presentation.save(path)
    contract = infer_deliverable_contract(
        f"Create a {kind.upper()} professional report", []
    )

    report = run_output_qa(
        [path],
        contract=contract,
        config={"enabled": True, "render": True},
        out_dir=tmp_path / "render",
        task_text=f"Create a {kind.upper()} professional report",
    )

    assert report.ok is True, report.blocking_errors
    assert report.render_reports[0]["rendered_images"]


def test_output_qa_disabled_is_noop(tmp_path):
    fitz = pytest.importorskip("fitz")
    pdf = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf))
    doc.close()
    rep = run_output_qa([pdf], config={"enabled": False}, out_dir=tmp_path / "r")
    assert rep.enabled is False
    assert rep.ok is True
    assert rep.render_reports == []


def test_vision_qa_with_fake_client(tmp_path):
    pytest.importorskip("fitz")
    pdf = tmp_path / "doc.pdf"
    _make_pdf(pdf, ["Content here"])

    class _Msg:
        content = '{"visual_ok": false, "issues": ["text too small"], "suggested_repair": "increase font"}'

    class _FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    from types import SimpleNamespace
                    return SimpleNamespace(choices=[SimpleNamespace(message=_Msg())])

    cfg = {"enabled": True, "render": True,
           "vision": {"enabled": True, "deployment": "fake", "max_images": 2}}
    rep = run_output_qa([pdf], config=cfg, out_dir=tmp_path / "r",
                        task_text="t", vision_client=_FakeClient())
    assert rep.vision_qa is not None
    assert rep.vision_qa["visual_ok"] is False
    # Non-blocking by default; surfaced as a warning.
    assert any("vision QA" in w for w in rep.warnings)
    assert rep.ok is True
