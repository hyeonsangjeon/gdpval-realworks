"""Tests for core/artifact_renderer.py + core/output_qa.py.

Render tests require PyMuPDF (skip gracefully otherwise). They never call an LLM:
vision QA is exercised only with a fake client.
"""

from pathlib import Path

import pytest

from core.artifact_renderer import render_artifact
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
    doc = fitz.open(); doc.new_page(); doc.save(str(pdf)); doc.close()
    c = infer_deliverable_contract("Produce a PDF report", [])
    rep = run_output_qa([pdf], contract=c, config={"enabled": True, "render": True},
                        out_dir=tmp_path / "r", task_text="Produce a PDF report")
    assert rep.ok is False
    assert any("blank" in e for e in rep.blocking_errors)


def test_output_qa_disabled_is_noop(tmp_path):
    fitz = pytest.importorskip("fitz")
    pdf = tmp_path / "blank.pdf"
    doc = fitz.open(); doc.new_page(); doc.save(str(pdf)); doc.close()
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
