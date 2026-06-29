"""Tests for core/deliverable_contract.py — inference, selection, validation."""

from pathlib import Path

import pytest

from core.deliverable_contract import (
    DeliverableContract,
    ContractValidation,
    infer_deliverable_contract,
    select_generated_artifacts,
    snapshot_dir,
    validate_contract,
)


# ── inference per type ────────────────────────────────────────────────────

@pytest.mark.parametrize("text,ext", [
    ("Create an Excel workbook summarizing Q3 sales", ".xlsx"),
    ("Build a PowerPoint deck for the board meeting", ".pptx"),
    ("Write a memo to the team about the new policy", ".docx"),
    ("Produce a one-page PDF flyer for the event", ".pdf"),
    ("Design a logo for the new startup brand", ".png"),
    ("Export the cleaned results as a CSV file", ".csv"),
    ("Generate a 30 second audio jingle for the ad", ".wav"),
    ("Render a short animation video of the logo", ".mp4"),
])
def test_infer_expected_extension(text, ext):
    c = infer_deliverable_contract(text, [])
    assert ext in c.expected_extensions, (text, c.expected_extensions)
    assert c.requires_deliverable is True
    assert c.min_count >= 1


def test_explicit_extension_token_is_high_confidence():
    c = infer_deliverable_contract("Save the output as a .csv file", [])
    assert c.confidence == "high"


def test_format_noun_only_is_medium_confidence():
    # "spreadsheet" can refer to an input file, so don't over-commit.
    c = infer_deliverable_contract("Summarize this spreadsheet of sales", [])
    assert c.confidence == "medium"
    assert ".xlsx" in c.expected_extensions


def test_csv_explicit_overrides_generic_spreadsheet():
    c = infer_deliverable_contract("Produce a spreadsheet exported as csv", [])
    assert ".csv" in c.expected_extensions
    assert ".xlsx" not in c.expected_extensions


def test_pdf_explicit_overrides_generic_report():
    c = infer_deliverable_contract("Write a report and deliver it as a PDF", [])
    assert ".pdf" in c.expected_extensions
    assert ".docx" not in c.expected_extensions


def test_config_can_pin_expected_extensions():
    c = infer_deliverable_contract("do the thing", [], {"expected_extensions": ["xlsx"]})
    assert c.expected_extensions == [".xlsx"]
    assert c.confidence == "high"


def test_no_signal_low_confidence_but_still_requires_file():
    c = infer_deliverable_contract("Create the deliverable for the client", [])
    assert c.expected_extensions == []
    assert c.confidence == "low"
    assert c.requires_deliverable is True  # creation verb present


# ── selection / reference exclusion ───────────────────────────────────────

def test_reference_xlsx_not_counted_as_generated(tmp_path):
    ref = tmp_path / "input_data.xlsx"
    ref.write_bytes(b"PK\x03\x04ref")
    gen = tmp_path / "report.xlsx"
    gen.write_bytes(b"PK\x03\x04gen")
    artifacts = select_generated_artifacts(tmp_path, reference_files=[str(ref)])
    names = {a.name for a in artifacts}
    assert "report.xlsx" in names
    assert "input_data.xlsx" not in names


def test_before_snapshot_excludes_preexisting(tmp_path):
    pre = tmp_path / "already_here.txt"
    pre.write_text("old")
    before = snapshot_dir(tmp_path)
    new = tmp_path / "fresh.pdf"
    new.write_bytes(b"%PDF-1.4")
    artifacts = select_generated_artifacts(tmp_path, [], before_snapshot=before)
    names = {a.name for a in artifacts}
    assert "fresh.pdf" in names
    assert "already_here.txt" not in names


def test_reserved_control_files_excluded(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    (tmp_path / "solution.py").write_text("print(1)")
    (tmp_path / "out.docx").write_bytes(b"PK\x03\x04")
    names = {a.name for a in select_generated_artifacts(tmp_path, [])}
    assert names == {"out.docx"}


# ── validation ────────────────────────────────────────────────────────────

def test_validate_missing_deliverable_is_blocking(tmp_path):
    c = infer_deliverable_contract("Create a PDF report", [])
    v = validate_contract(c, [])
    assert v.ok is False
    assert any("at least" in e for e in v.blocking_errors)


def test_validate_wrong_primary_high_confidence_blocks(tmp_path):
    docx = tmp_path / "out.docx"
    docx.write_bytes(b"PK\x03\x04")
    c = infer_deliverable_contract("Export results as a .xlsx file", [])  # high
    v = validate_contract(c, [docx])
    assert v.ok is False
    assert any(".xlsx" in e for e in v.blocking_errors)


def test_validate_wrong_primary_medium_confidence_only_warns(tmp_path):
    docx = tmp_path / "out.docx"
    docx.write_bytes(b"PK\x03\x04")
    c = infer_deliverable_contract("Make a spreadsheet of the data", [])  # medium
    v = validate_contract(c, [docx])
    assert v.ok is True  # not blocking at medium confidence
    assert v.warnings


def test_validate_matching_primary_passes(tmp_path):
    xlsx = tmp_path / "report.xlsx"
    xlsx.write_bytes(b"PK\x03\x04data")
    c = infer_deliverable_contract("Export as .xlsx", [])
    v = validate_contract(c, [xlsx])
    assert v.ok is True
    assert v.matched_primary == ["report.xlsx"]


def test_validate_empty_file_does_not_count(tmp_path):
    empty = tmp_path / "report.xlsx"
    empty.write_bytes(b"")
    c = infer_deliverable_contract("Export as .xlsx", [])
    v = validate_contract(c, [empty])
    assert v.ok is False  # 0 non-empty files


def test_contract_prompt_section_has_no_format_braces():
    c = infer_deliverable_contract("Build a PowerPoint deck", [])
    section = c.to_prompt_section()
    assert "{" not in section and "}" not in section
    assert "DELIVERABLE CONTRACT" in section
