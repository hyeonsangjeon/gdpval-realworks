# HEADLESS RENDER PROBE

## One-Line Conclusion

Mac mini/display hardware is not needed for this path. Headless rendering worked for xlsx, docx, and pptx using LibreOffice `--headless` to PDF plus PyMuPDF to PNG. The current environment is macOS, not Linux, so `apt-get` itself was not executed; a Linux/GitHub Actions runner should install `libreoffice`, `fonts-noto`, `fonts-noto-cjk`, `fonts-liberation`, and `PyMuPDF`. Font/tofu blocker was not observed for the xlsx/docx/pptx probe; the observed square-like defect in the PDF control appears to be baked into the source PDF/font mapping, not caused by missing render fonts.

Next blocker: Azure/vision path and file-selection routing, not headless rendering.

## Environment

| Probe | Result |
|---|---|
| OS | `Darwin hsjeonui-MacBookAir.local 25.5.0 ... RELEASE_ARM64_T8132 arm64` |
| `apt-get` | Not available in this macOS environment |
| Install path used | `brew install --cask libreoffice`; `.venv/bin/python -m pip install PyMuPDF` |
| LibreOffice | `LibreOffice 26.2.3.2 70e089b17412e4cb7773e41413306b17a2328c34` |
| PyMuPDF | `PyMuPDF 1.27.2.3` |
| Headless/display | `soffice --headless --convert-to pdf`; no X server/display launched |

Linux CI note: this local run cannot prove `apt-get` package availability because the active runner is macOS. The equivalent GitHub Actions setup should be:

```bash
sudo apt-get update
sudo apt-get install -y libreoffice fonts-noto fonts-noto-cjk fonts-liberation
python -m pip install PyMuPDF
```

## Render Results

All files were downloaded from:

`https://huggingface.co/datasets/HyeonSang/exp003_GPT52Chat_baseline_runner_exec/resolve/main/...`

| Case | Kind | Task | Source deliverable | Convert | Pages | PNGs |
|---|---|---|---|---:|---:|---|
| `xlsx_83d10b06_sample` | xlsx | `83d10b06` | `deliverable_files/83d10b06-26d1-4636-a32c-23f92c57f30b/Sample.xlsx` | success, 4.91s | 35 | 6 sampled |
| `docx_6dcae3f5_email` | docx | `6dcae3f5` | `deliverable_files/6dcae3f5-bf1c-48e0-8b4b-23e6486a934c/Email_to_PD_Key_Indicator_Analysis.docx` | success, 3.54s | 10 | 6 sampled |
| `pptx_a74ead3b_recovery` | pptx | `a74ead3b` | `deliverable_files/a74ead3b-f67d-4b1c-9116-f6bb81b29d4f/Session_14_Nurturing_Parenting_Recovery.pptx` | success, 2.66s | 4 | all 4 slides |
| `pdf_27e8912c_ergonomics_tofu_control` | pdf control | `27e8912c` | `deliverable_files/27e8912c-8bd5-44ba-ad87-64066ea05264/Workstation_Ergonomics_Checklist.pdf` | input PDF, no LO | 2 | both pages |

Representative PNG paths:

- `tasks/0601_monday/render_probe/png/xlsx_83d10b06_sample_p01.png`
- `tasks/0601_monday/render_probe/png/docx_6dcae3f5_email_p01.png`
- `tasks/0601_monday/render_probe/png/pptx_a74ead3b_recovery_p01.png`
- `tasks/0601_monday/render_probe/png/pptx_a74ead3b_recovery_p02.png`
- `tasks/0601_monday/render_probe/png/pdf_27e8912c_ergonomics_tofu_control_p01.png`

Full machine manifest:

- `tasks/0601_monday/render_probe/manifest.json`

## Render Quality

### XLSX: `83d10b06 / Sample.xlsx`

Result: rendered, nonblank, readable enough for visual judging.

Observed quality:

- The sheet renders as a real table, not a blank page.
- No tofu/box glyphs were visible in the sampled PNGs.
- Formatting defects are visible: narrow columns, truncated headers, clipped KRI/entity text, and a plain spreadsheet dump appearance.
- This is enough for a vision model to distinguish "file exists and table-like" from "professionally formatted workbook".

Interpretation: v1's `5/5` likely over-credits table presence; v2's stricter concern about formatting/column widths is visually inspectable.

### DOCX: `6dcae3f5 / Email_to_PD_Key_Indicator_Analysis.docx`

Result: rendered, nonblank, readable enough for visual judging.

Observed quality:

- Text renders cleanly; no tofu/box glyphs were visible.
- The owner-noted defect is visible: repeated `None (None)` resident identifiers dominate the document.
- Broken wrapping is visible around repeated phrases like `Total Key / Indicators, Total Case / Numbers`.
- This is not a render-font problem. It is a source deliverable/data-merge defect made visible by rendering.

Interpretation: headless rendering exposes the blocking defect that a plain metadata extractor can miss.

### PPTX: `a74ead3b / Session_14_Nurturing_Parenting_Recovery.pptx`

Result: rendered, nonblank, all 4 slides available.

Observed quality:

- Slide text and background render cleanly.
- No tofu/box glyphs were visible.
- The owner-noted design issue is visible: repeated pale-blue circular decoration, large empty space, and low-design slide system.
- Slide 1 title is visibly clipped on the right (`Moving Forward wit`), indicating a real layout/text-box defect or LibreOffice-compatible layout exposure.

Interpretation: pptx visual/style defects are observable from the generated PNGs. This is the critical proof point for a future vision judge path.

### PDF Control: `27e8912c / Workstation_Ergonomics_Checklist.pdf`

Result: rendered directly by PyMuPDF, nonblank.

Observed quality:

- The page renders clearly, including title, table, checklist, and appendix diagram.
- Square-like glyphs are visible in strings such as `Self■Assessment` and `Chair■Neutral`.
- This was not produced by LibreOffice conversion; the source is already PDF and was rendered directly with PyMuPDF.
- PyMuPDF font inspection shows standard PDF fonts including `Helvetica`, `Helvetica-Bold`, `Helvetica-Oblique`, and `ZapfDingbats`; the extraction around the defect is abnormal (`SelfIAssessment`), supporting source PDF/font-map defect rather than missing system fonts.

Interpretation: for this control, the square-like glyph issue is a deliverable/PDF encoding defect, not a headless render environment artifact. Installing additional fonts is unlikely to remove this specific defect. Linux should still install Noto/Liberation/CJK fonts for broad coverage, especially non-English docs.

## Decision

Headless rendering is viable for the visual formatting track:

- xlsx/docx/pptx all converted to PDF with `soffice --headless`.
- PyMuPDF rendered PNGs without display/X server.
- The resulting PNGs are informative enough to show table truncation, DOCX merge leakage, PPTX layout/design problems, and PDF glyph defects.

Mac mini hardware is not required. A Linux runner should be sufficient if the job installs LibreOffice, PyMuPDF, and broad fonts. The remaining implementation work is:

1. File selection: choose the actual candidate deliverable, not echoed reference files.
2. Snapshot policy: choose pages/sheets/slides deterministically and cap large workbooks.
3. Vision judge integration: send rendered PNGs to the grader once Azure auth/model path is restored.
4. Font hardening: install Noto/Liberation/CJK on Linux and keep a small tofu regression fixture.

