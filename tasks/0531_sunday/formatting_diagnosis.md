# FORMATTING JUDGE DIAGNOSIS

## 한 줄 결론

formatting 후퇴 주원인: **holistic rubric과 저수준 `inspect_formatting` 증거의 mismatch + v1-mini의 content-based leniency** / formatting 채점 전반 신뢰도: **낮음-중간** / 다음 권고: **perception 마무리보다 formatting validator/renderer 진단을 우선**. v2-mini의 3건 후퇴가 반드시 오판이라는 증거는 없고, v1-mini가 실제 formatting 속성이 아닌 내용 스니펫으로 pass한 신호가 더 강하다.

## PHASE A — 후퇴 3건 해부

| task | deliverable kinds | v1-mini | v2-mini | v2-standard | 메커니즘 |
|---|---|---|---|---|---|
| `83d10b06` | `Sample.xlsx`, `Population v2.xlsx` | pass 5.0, evidence: sheet/header text from `Selected Sample` | partial 1.5, evidence: `"merged_ranges": [], "column_widths": {}, "has_charts": false` | fail 0.0, evidence: cell style tuple with default fill/bold/border and openpyxl color error text | **same criterion, different evidence class.** v1 treats tabular content/headers as style; v2 sees sparse formatting metadata and downgrades. Also file set includes reference workbook, so path ambiguity is possible. |
| `7b08cd4d` | final `.xlsx` plus reference `.xlsx` | pass 5.0, evidence: report title and `Revenue` text | partial 3.0, evidence: column widths A-F all `22.0` | partial 3.0, evidence: same widths plus empty merged ranges | **v1 content-as-style pass; v2 low-level style metadata partial.** v2 evidence supports some formatting but not enough for holistic style. |
| `27e8912c` | checklist PDF, action-items DOCX, 3 PNGs | pass 5.0, evidence: checklist title and goal text | partial 3.5, evidence: DOCX `style_histogram` | partial 4.0, evidence: same `style_histogram` | **v1 content-as-style pass; v2 structural style histogram partial.** Rubric is broad enough that both could be defensible without human gold. |

Classification: all 3 are **not** evidence-free failures. They are mostly `(i) same broad criterion, different evidence/interpretation`, with `(ii) v2 evidence too low-level or incomplete` as a contributing cause. None are fixed by vision/audio perception because the modality is `formatting`, not `visual` or `audio`.

## PHASE B — 코드 경로

### Routing

- `batch-runner/core/grader_routing.py:56-71` defines formatting keywords: `format`, `formatted`, `formatting`, `style`, `styles`, `styling`, `structure`, `structured`, `presentation`, `polish`, `polished`, `template`.
- `batch-runner/core/grader_routing.py:88-122` routes visual first, then audio, then formatting; formatting gets `preferred_op="inspect_formatting"`.
- Full-220 formatting bucket: **539/10,453** items. Critical formatting: **157/483** items.
- Critical formatting is dominated by broad style rubrics: rough category count is **140/157 `Overall formatting and style of the deliverable`**, then 9 template, 4 file-format, 3 other, 1 tabular-structure.
- Precheck barely covers this surface: copied `PRECHECK_PATTERNS` from `batch-runner/core/grader.py:82-98`; only **4/157 critical formatting** match precheck-like file extension/name checks. The rest go to judge.

Routing assessment: high precision for broad style/form criteria, but it overcaptures some non-style uses of “format/style” in the all-item set, e.g. bit-depth/format, citation style, narrative-style treatment. This overcapture is not the main critical problem because critical items are mostly the explicit overall-style rubric.

### `inspect_formatting` 충실도

- Tool catalog tells the judge to use `inspect_formatting` for “style, fills, borders, layout, merged cells, charts” (`batch-runner/prompts/grader_judge_v2.md:44-49`).
- XLSX path returns merged ranges, column widths, chart presence, and a sample of cells with fill/bold/font_color/border (`batch-runner/core/tools/read_deliverable.py:359-415`).
- DOCX path returns only paragraph/table/section counts and style histogram (`batch-runner/core/tools/read_deliverable.py:418-433`).
- PPTX path returns slide layout names and shape type counts (`batch-runner/core/tools/read_deliverable.py:436-451`).
- PDF path returns page count and font names only (`batch-runner/core/tools/read_deliverable.py:462-473`).
- `render_to_image` explicitly does not support XLSX/DOCX/PPTX without LibreOffice (`batch-runner/core/tools/read_deliverable.py:538-540`), so the grader cannot visually inspect spreadsheet/doc layout unless the deliverable is PDF/image.

충실도 평가: XLSX support is useful but incomplete; it omits number formats, date/currency formatting, conditional formatting, alignment, row heights, freeze panes, print/page layout, and rendered appearance. DOCX/PDF/PPTX support is too shallow for “overall style” beyond coarse structure/font metadata.

## PHASE C — 157 critical formatting 신뢰도

Source: `data/grades/exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-mini__11e7900__v1__v2sm.json` for full-220; v2 has only N=10 existing data.

### Full-220 v1-mini critical formatting

| metric | value |
|---|--:|
| critical formatting items | 157 |
| verdicts | pass 107 / partial 38 / fail 12 |
| sign-aware right | true 106 / false 51 |
| strong formatting-attribute evidence | 0 / 157 |
| structure/file evidence | 27 / 157 |
| content/text evidence | 130 / 157 |

This is the strongest reliability warning. The current default’s formatting-critical pass rate is mostly supported by content snippets, not actual formatting attributes. Examples include report titles, sheet headers, and prose excerpts used as evidence for “Overall formatting and style.”

### Existing v2 N=10 formatting slice

| run | critical formatting n | verdicts | evidence class |
|---|--:|---|---|
| v2-mini | 6 | pass 1 / partial 4 / fail 1 | 6/6 strong formatting attrs |
| v2-standard | 6 | pass 1 / partial 4 / fail 1 | 6/6 strong formatting attrs |

v2 is better grounded on this narrow slice, but not necessarily more accurate. Its evidence is often too atomic for holistic style: e.g. `column_widths`, empty `merged_ranges`, `style_histogram`, or default fill/border values. That explains why v2-standard and v2-mini agree on the formatting regression direction while v1-mini passes.

### Evidence validity read

- v1-mini full-220: **low** for formatting validity. It often answers formatting with text/content evidence.
- v2 N=10: **medium** for grounding, **low-medium** for holistic judgment. It cites actual formatting metadata, but the metadata is too narrow to prove professional layout/style.
- Without human gold, the 3 “regressions” should be treated as **v1-vs-v2 disagreement**, not automatically v2 mistakes.

## 원인 가설

1. **Holistic style rubric vs low-level tool output mismatch.**  
   Evidence: all 3 regressions are `Overall formatting and style`; v2 evidence is `merged_ranges`, `column_widths`, `style_histogram`, or cell style snippets. Code confirms XLSX/DOCX/PDF/PPTX formatting outputs are coarse and not rendered.

2. **v1-mini likely inflated formatting by using content snippets as style evidence.**  
   Evidence: full-220 critical formatting has **130/157 content/text evidence** and **0/157 strong formatting-attribute evidence**. In all 3 regressions, v1 passes using titles/headers/prose rather than formatting metadata.

3. **`inspect_formatting` misses important formatting dimensions.**  
   Evidence: code captures no number format, currency/date format, conditional formatting, alignment, row height, or rendered workbook/doc appearance. This directly affects criteria such as currency/date formatting and conditional flags.

4. **Candidate file list can include reference files, creating path ambiguity.**  
   Evidence: `83d10b06` lists both `Sample.xlsx` and `Population v2.xlsx`; `7b08cd4d` lists final workbook plus `Fall Music Tour Ref File.xlsx`. The prompt says all listed files were produced by the model, but some are reference/input files. Grade evidence does not record the path used, so later audit cannot prove which file was inspected.

5. **Formatting classifier has broad keyword overcapture, but it is secondary.**  
   Evidence: all-formatting bucket includes non-layout uses like bit-depth “format”, citation “style”, and narrative-style treatment. However critical formatting is mostly explicit `Overall formatting and style`, so classifier overcapture is not the main regression driver.

## owner 결정 필요 / 다음 트랙

1. **Do not revive v2-mini flip from formatting data.** The formatting evidence does not support default flip; it weakens both v1-mini and v2-mini claims.
2. **Formatting should get the next diagnostic/fix track before perception polish.** Critical formatting is 157 items, while critical visual+audio is 29 items.
3. **Add path/tool instrumentation before any future grading run.** Record `tools_used`, `path_used`, `op_used`, and maybe a compact `formatting_features_used` per item; current grade evidence alone is not auditable enough.
4. **Upgrade formatting evidence surface.** For XLSX, include number formats, conditional formatting, alignment, row heights, freeze panes, sheet views, and print/page setup. For DOCX/PDF/PPTX, either render to image or expose richer layout/font/table metadata.
5. **Hand-grade target should shift.** If gold work is done, prioritize the 140 `Overall formatting and style` critical items or a stratified sample of them, not only the 19 visual/audio candidates.
