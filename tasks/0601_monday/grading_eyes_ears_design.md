# GRADING EYES & EARS - DESIGN

## 한 줄 결론

Step 1 기준 self-contained는 전체 10,053/10,453(96.2%), critical 330/483(68.3%)다. 설계는 두 갈래다. (1) self-contained + objective criterion은 추출환경(A) + rubric 판정 skill(B)의 주력 대상이다. (2) critical ambiguous 141개 중 거의 전부인 140개 `Overall formatting and style`은 추출 필드 추가만으로 닫히지 않으며, rubric decomposition + judge-visible render snapshots + gold sample이 필요한 별도 트랙이다. 구현 무게는 audio/text/objective formatting은 가벼움-중간, Office render + overall-style 판정은 무거움이다. mini vs gpt-5.4 적합성은 A+B 적용 뒤 gold/stratified audit로 측정해야 하며 지금 예단하지 않는다.

## 설계 원칙

1. A와 B를 분리한다.
   A는 task-agnostic evidence extractor다. task id나 rubric 정답을 모르고, 파일에서 구조/텍스트/형식/시각/청각 facts만 추출한다.
   B는 rubric-aware grading skill이다. 런타임에 HF `rubric_json`을 받아 criterion별로 어떤 evidence를 봐야 하는지 결정한다.
2. skill에 task별 rubric 내용을 정적으로 굽지 않는다.
   skill에는 modality별 검증 절차, evidence schema, verdict calibration만 둔다. task별 criterion은 `RubricLoader`가 HF에서 fetch하고 `rubric_sha`를 기록한다.
3. 정답 출처는 rubric이다.
   `deliverable_files`는 100점 gold가 아니고 일부 media는 null/불완전할 수 있으므로, deliverable 자체를 정답으로 취급하지 않는다.
4. self-contained를 먼저 자동화한다.
   reference-requiring 203/10,453(1.9%)와 critical 12/483(2.5%)는 작지만 별도 reference path가 필요하다. 이들을 deliverable-only extractor로 억지 판정하면 오히려 leniency가 생긴다.
5. holistic formatting은 별도 취급한다.
   critical formatting 157개 중 141개가 ambiguous이고, 그중 140개가 사실상 같은 문구인 `Overall formatting and style of the deliverable`이다. "눈/귀"의 핵심 성공 조건은 perception 호출 수가 아니라, 이 broad rubric을 objective dimensions와 rendered evidence로 엄중하게 다루는 것이다.

## 핵심 분기: 두 개의 다른 문제

이 설계에서 #1과 #2를 같은 "추출 필드 추가" 문제로 합치지 않는다.

| Track | 대상 | Step 1 근거 | extractor의 역할 | judge/skill의 역할 | gold 필요 |
|---|---|---:|---|---|---|
| 1. Objective self-contained | 파일 형식, count/value, sample rate, clipping, number format, required sheets/slides/pages, explicit text/table/code checks | 전체 self-contained 96.2%, critical self-contained 68.3% | 판정 가능한 facts를 뽑고 일부는 deterministic verdict까지 낸다 | rubric text와 facts를 연결해 pass/partial/fail calibration | fixture/unit test 중심, human gold는 spot-check |
| 2. Overall-style adjudication | `Overall formatting and style of the deliverable` | critical ambiguous 141개 중 140개 | raw facts와 rendered snapshots를 제공할 뿐, 단독 pass/fail 판정하지 않는다 | broad criterion을 측정 가능한 차원으로 분해하고 rendered evidence를 보고 판단한다 | 1순위. 140개 전체 또는 stratified sample 필요 |

Track 2의 핵심은 "더 많은 formatting fields"가 아니다. number format, row height, conditional formatting 같은 fields는 supporting evidence일 뿐이다. `Overall formatting and style`은 deliverable 전체의 rendered appearance와 professional/readable/layout 품질을 묻기 때문에, decomposition rule과 visual snapshot 없이는 엄중한 판정이 불가능하다.

## PART A - 추출 환경

### 현재 자산

- `read_deliverable`는 이미 `inspect_structure`, `read_content`, `inspect_formatting`, `render_to_image`, `probe_audio`, `probe_video`를 제공한다.
- `probe_audio`/`probe_video`는 PyAV 기반이라 ffmpeg system binary 없이 기본 metadata, peak, silence ratio를 뽑을 수 있다.
- `render_to_image`는 현재 PDF/image만 지원한다. XLSX/DOCX/PPTX render는 LibreOffice headless가 필요해서 v2 scope 밖으로 남아 있다.
- `inspect_formatting`은 XLSX의 merged ranges, column widths, chart presence, styled cell sample 정도는 보지만 number format, conditional formatting, alignment, row height, freeze panes, print setup이 빠져 있다. DOCX/PPTX/PDF는 style histogram, shape counts, fonts 수준이라 holistic style에 빈약하다.
- `VisionPerception`/`AudioPerception`은 routing된 item에 sub-judge를 붙일 수 있고 `tools_used`/`perception_called` instrumentation은 이미 일부 있다.

### Audio

Step 1 coverage: 전체 audio 108/120 self-contained, critical audio 13/17 self-contained.

| Extracted evidence | Covers criterion type | Library / backend | Verdict rule |
|---|---|---|---|
| container, codec, extension, bitrate if available | WAV/MP3/AAC/losless-vs-lossy, file-format constraints | PyAV, mutagen, optional ffprobe | exact match or allowed-set check |
| duration, sample rate, channel count, bit depth | "48 kHz", stereo/mono, length windows | PyAV, soundfile | numeric tolerance check |
| peak, clipping count, clipping duration | no clipping / clipping suspected | PyAV frame scan, soundfile/numpy | fail if samples exceed threshold, partial if isolated peaks |
| integrated LUFS, short-term LUFS, true peak | loudness target / balance constraints | pyloudnorm, numpy | pass/partial/fail by tolerance band |
| silence ratio, leading/trailing silence, silent gaps | no long silence, fade-in/out sanity | numpy/scipy | compare against explicit time threshold |
| band energy / spectral centroid / noise floor | presence/clarity/noise style absolute checks | librosa/scipy | evidence only unless criterion gives threshold |
| tempo/key/onset stats | BPM/key when explicitly bounded | librosa | pass only when tolerance is objective |

Audio sub-judge policy:

- For objective audio facts, prefer deterministic extractor verdict and give the LLM the measurements.
- Use `gpt-audio-1.5` only when the criterion asks for audible quality that is not reducible to current metrics: voice quality, music style, mix clarity, masking, emotional tone.
- Keep `AudioPerception` as a secondary judge, not the primary fact source. Its evidence should cite audible observations and must include `audio_path`, clip duration sent, and whether the whole file or first 30 seconds was judged.
- Reference-requiring audio items such as `ff85ee58` final mix vs `TAVARUA_MUSIC ONLY.wav` need a reference bundle and alignment/cross-correlation path. They should be marked `needs_reference` until that exists.

### Visual

Step 1 coverage: 전체 visual 400/414 self-contained, critical visual 12/12 self-contained.

| Extracted evidence | Covers criterion type | Library / backend | Verdict rule |
|---|---|---|---|
| PDF/image render PNG | charts, layout, logos, images, screenshot checks | PyMuPDF, Pillow | required precondition for visual sub-judge |
| XLSX/DOCX/PPTX rendered pages/slides/sheets | spreadsheet/doc/deck appearance | LibreOffice headless + PyMuPDF/Pillow | needed before vision can inspect Office artifacts |
| OCR text boxes and positions | visible labels, titles, axis labels, slide text | OCR model or Tesseract if available | text presence + bounding box sanity |
| chart metadata from OOXML | chart count/type, axes, titles, series | openpyxl/python-pptx/XML | deterministic check before vision |
| image/logo metadata | image count, dimensions, placement, alt/caption | OOXML + Pillow | deterministic for presence/size |
| color/font/layout metrics | color use, font size contrast, overlap/clipping | OOXML + rendered image analysis | facts for judge, direct verdict only with objective threshold |

Visual sub-judge policy:

- `render_to_image` must support Office artifacts before visual grading is benchmark-wide useful. Without that, visual sub-judge only sees PDFs/images and misses many spreadsheet/deck/doc visual criteria.
- For visual criteria, extractor should provide both structured facts and one or more render thumbnails. The LLM/vision judge should answer from the rendered evidence, not from filenames or text-only snippets.
- Reference-requiring visual items, mostly floor layout/reference image/logo/template comparisons, need a reference render side-by-side or embedding comparison. Mark them `needs_reference_visual`.

### Formatting

Step 1 coverage: 전체 formatting 387/539 self-contained, critical formatting only 15/157 self-contained; critical formatting 141/157 ambiguous.

| Extracted evidence | Covers criterion type | Current gap |
|---|---|---|
| XLSX number/date/currency/percent formats | "B column is currency/date formatted" | missing |
| formulas vs hard-coded values, formula ranges | spreadsheet calculation integrity | partial through read values only |
| conditional formatting rules | highlight/flag/color-by-rule criteria | missing |
| alignment, wrap text, indentation, merged cells | tabular readability / header layout | merged only partial |
| row heights, column widths, hidden rows/cols | layout density and printable structure | column width partial only |
| freeze panes, filters, tables, pivots, charts | workbook usability criteria | charts partial only |
| page setup, print area, orientation, margins | printable PDF/spreadsheet requirements | missing |
| cell protection/data validation | editable vs locked template fields | missing |
| DOCX styles, margins, section breaks, tables, images | legal/report/document style | style histogram only |
| PPTX slide sizes, layouts, fonts, colors, placeholders, images | deck professionalism/readability | shape type counts only |
| rendered Office pages | holistic style, readability, overlap | missing without LibreOffice |

Formatting design:

- Add `inspect_formatting_v2` fields for Track 1 objective formatting rather than replacing the existing op immediately. Keep old schema stable, add nested `formatting_v2` with explicit fields.
- Split verdict logic into two lanes:
  - Objective formatting lane: number formats, page count, required columns, freeze panes, protection, conditional formatting, named sheets. These can produce deterministic pass/fail evidence.
  - Overall-style lane: the 140 critical `Overall formatting and style` items. This should never be auto-pass from one low-level fact, and should not be treated as solved by adding more extractor fields. It needs decomposition dimensions plus judge-visible render snapshots.
- Holistic lane should output a dimension vector, not one vague evidence string:
  - `layout_consistency`
  - `readability`
  - `visual_hierarchy`
  - `spacing_density`
  - `format_appropriateness`
  - `render_integrity`
  - `blocking_defects`
- The broad criterion can pass only when no blocking defects exist and most dimensions are adequate. Partial is the default when evidence is mixed. Fail requires a concrete rendered/structural defect.
- Objective formatting fields cover the 15/157 critical self-contained formatting items and support the 140 overall-style items. They do not close the overall-style rubric by themselves.

### Text

Step 1 coverage: 전체 text 9,158/9,380 self-contained, critical text 290/297 self-contained.

Text is not "eyes/ears", but it should stay in A because many formatting/visual/audio criteria depend on file selection and content context.

- Extract file tree, MIME/kind, filenames, sizes.
- Extract PDF/DOCX/PPTX/XLSX text with location metadata where possible: page, slide, sheet, row/column.
- Extract tables as structured rows/cells, not only CSV-like text.
- Run deterministic count/value checks when criterion has explicit thresholds.
- Keep code artifacts readable with file listing, syntax parse, and small snippets. Do not route source-code presence through "reference source file" logic unless rubric names a reference file.

### Container / runtime image spec

This step does not build an image. Proposed grading runtime image:

- Base: Ubuntu LTS or slim Python 3.11 image compatible with GitHub Actions and local runner.
- Python deps: existing `batch-runner/requirements.txt`, plus explicit `soundfile`, `pyloudnorm`, `librosa`, `scipy`, `numpy`, `mutagen`, `Pillow`, `PyMuPDF`, `openpyxl`, `python-docx`, `python-pptx`.
- System deps: `libreoffice`, `libreoffice-calc`, `libreoffice-writer`, `libreoffice-impress`, `fonts-noto`, `fonts-liberation`, `fontconfig`, `ffmpeg`, `libsndfile1`.
- Optional deps: `tesseract-ocr` for OCR, `poppler-utils` only if PyMuPDF render is insufficient, not as default.
- Packaging: publish to GHCR as a grading-runner image. Pin image digest in workflow for auditability.
- Runtime preflight: at job start, print versions for LibreOffice, PyAV, soundfile, PyMuPDF, openpyxl, and available fonts. Fail closed for required extractor lanes; degrade gracefully only for optional OCR.

## PART B - skill 구조 + 동적 rubric 로더

### Skill shape

The skill should be a static procedure, not a static answer key.

```
grading-eyes-ears/
  SKILL.md
  recipes/
    audio.md
    visual.md
    formatting.md
    text.md
    holistic_formatting.md
  schemas/
    evidence_bundle.schema.json
    criterion_decision.schema.json
  scripts/
    classify_nature.py
    summarize_evidence.py
```

Skill duties:

- Given one criterion, classify modality via `classify_criterion` and nature via the Step 1 self-contained/reference/ambiguous rules.
- Select the evidence family:
  - audio metrics
  - render/vision
  - formatting structure
  - text/table/code
  - reference comparison
  - holistic formatting dimensions
- Tell the judge which evidence is sufficient, which is only supporting, and which missing evidence should force `judge_error` or partial/fail.
- Preserve negative-score semantics: for penalty items, `pass` means violation exists and score is subtracted. The skill must never flatten sign-aware grading back into "pass means good".

### Dynamic rubric injection

Do not copy task rubrics into skill files.

Runtime flow:

1. `RubricLoader(repo_id="openai/gdpval", revision=<configured>)` loads the task rubric from HF/local cache.
2. Loader records:
   - `rubric_repo_id`
   - `rubric_revision`
   - `rubric_sha`
   - `task_id`
   - `rubric_item_id`
   - normalized criterion text
3. Grader computes routing/nature per criterion at runtime.
4. Evidence extractor builds a task-level evidence bundle from deliverables and, if allowed, reference files.
5. Judge receives:
   - one criterion or a small evidence-family batch
   - relevant evidence slice
   - skill recipe
   - rubric sha/version
6. Grade JSON stores the rubric metadata per task and per item.

This keeps HF rubric as the single source of truth. If the rubric changes, the same skill follows the new criterion text and the run is auditable by SHA.

### Evidence bundle contract

Each task should produce a compact evidence bundle before item grading where feasible:

```json
{
  "task_id": "...",
  "rubric_sha": "...",
  "deliverables": [
    {
      "path": "Sample.xlsx",
      "kind": "xlsx",
      "structure": {},
      "text_index": {},
      "formatting": {},
      "renders": [],
      "audio": null,
      "video": null
    }
  ],
  "reference_files": [],
  "extractor_versions": {},
  "warnings": []
}
```

Per-item judge input should be an evidence slice, not the full raw bundle. This controls token cost and makes mini-vs-standard comparison fairer.

### Overall-style boundary

`Overall formatting and style` is not a free-form vibe check and not a deterministic extractor target. It is the dominant critical ambiguous bucket: 140 repeated criteria, nearly all of the 141 critical ambiguous items. The skill should force a structured assessment, but the final verdict remains an adjudication over rendered evidence.

| Dimension | Evidence source | Example blocking defect |
|---|---|---|
| File/render integrity | structure + render | requested PDF/deck/workbook absent or unreadable |
| Layout consistency | rendered pages + formatting attrs | wildly inconsistent headings/tables |
| Readability | rendered pages + OCR/font sizes | text overlaps, clipped labels, tiny unreadable text |
| Visual hierarchy | styles/fonts/spacing | no discernible headings/sections in a report/deck |
| Data/table legibility | sheet render + widths/heights | columns truncated or tables unusable |
| Professional finish | render + metadata | obvious default dump, broken charts, empty slides |

Rubric decomposition rule:

1. First require artifact sanity: correct requested file type, opens successfully, non-empty, and renderable.
2. Then assess all dimensions above using rendered snapshots as primary evidence and structural fields as support.
3. Treat content presence as insufficient. A report title, table header, or slide text can support "not empty", but cannot prove overall style.
4. Pass requires positive evidence across most dimensions and no blocking defect.
5. Partial is the default when evidence is incomplete, mixed, or only low-level fields are available.
6. Fail requires concrete rendered/structural defects such as unreadable text, broken layout, empty/default-looking deliverable, missing requested artifact, or severe table/chart clipping.

Judge-visible render snapshot design:

- Every Office artifact in this lane needs at least one representative render: first page/slide/sheet, plus pages/sheets likely to contain tables/charts.
- XLSX should render selected sheets to image with visible grid/table/chart state, not only expose `column_widths`.
- DOCX/PDF should render first page plus pages containing major tables/figures.
- PPTX should render all slides for short decks or a bounded sample for long decks.
- Snapshot metadata must include path, page/sheet/slide, render backend, dimensions, and any render warnings.
- The judge must cite the snapshot location or a structural field. Evidence like "contains a title" is not enough for this criterion.

Gold priority:

- The first gold target for strict grading is not the 19 visual/audio candidates. It is the 140 `Overall formatting and style` critical items, or a stratified sample of them by artifact type (XLSX/DOCX/PPTX/PDF) and current verdict disagreement.
- Gold labels should record dimension-level notes, not only pass/fail. Otherwise the decomposition cannot be calibrated.

### Lightweight model suitability

A+B can make a smaller model viable only if evidence is already clean, compact, and task-scoped. Measurement plan:

- Hold task set, rubric sha, evidence bundle, and prompt constant.
- Compare mini vs standard on the same evidence slices.
- Primary metric: item-level agreement with gold for objective self-contained criteria, critical-pass agreement for critical items, and false pass rate on negative/penalty items.
- Secondary metric: evidence validity: did the answer cite the right path/op/field/render?
- Escalation rule: use standard when criterion is reference-requiring, holistic formatting, audio/visual sub-judge disagreement, extractor error, high-stakes critical item with low confidence, or evidence bundle too sparse.

## PART C - instrumentation + verification

### Per-item fields to record

Current `ToolCallingResult` has `tools_used` and `perception_called`. Extend the audit surface:

| Field | Purpose |
|---|---|
| `routing_modality` | classifier result: visual/audio/formatting/text |
| `criterion_nature` | self-contained/reference-requiring/ambiguous |
| `preferred_op` | router suggestion |
| `tools_used` | all dispatched tools in order |
| `op_used` | normalized list of read_deliverable ops |
| `path_used` | exact deliverable path(s) inspected |
| `scope_used` | sheet/page/slide/range selected |
| `evidence_family` | audio_metrics, office_render, xlsx_formatting, text_table, reference_compare, holistic_formatting |
| `perception_called` | any vision/audio sub-judge used |
| `perception_model` | gpt-5.4 vision / gpt-audio-1.5 / none |
| `rubric_repo_id`, `rubric_revision`, `rubric_sha` | audit of grading basis |
| `extractor_version` | code/image version for evidence bundle |
| `extractor_errors` | missing dependency, render failure, corrupt file |
| `deterministic_verdict` | pass/fail/partial if rule-based check applies |
| `judge_verdict` | final LLM verdict |
| `evidence_validity` | tool-grounded, wrong-path, content-as-formatting, unsupported |

Path instrumentation is mandatory before more grading runs. The formatting diagnosis showed file lists can contain reference-like files, and current evidence does not prove which path was inspected.

### Verification plan

Use three validation lanes.

1. Deterministic self-contained checks
   - Targets: file extension/name, counts, sample rate, duration, channel count, number format, freeze panes, required sheets/pages/slides.
   - Validation: unit tests and fixture files; no gold LLM required.
   - Success: deterministic extractor verdict equals expected fixture verdict.

2. Human gold for holistic/reference criteria
   - Priority 1 target: the 140 critical `Overall formatting and style` items, or a stratified sample by artifact type and current v1/v2 disagreement.
   - Priority 2 target: reference-requiring critical items, audio mix/reference comparison items.
   - Use Step 1 priority:
     - critical ambiguous formatting: 141 items; 140 are the repeated overall-style rubric
     - critical reference-requiring: 12 items
     - critical audio reference subset: 4 items
   - Success: judge agreement with hand-grade improves without raising false pass rate.

3. Paired model evaluation after A+B
   - Run mini and standard on identical evidence bundles.
   - Stratify by modality/nature: objective self-contained, holistic formatting, reference-requiring, audio/visual.
   - Include at least one rubric-size monster and at least one Office-render-heavy task.
   - Do not use self-graded average score as the decision metric. Use gold agreement, critical false pass/fail, evidence validity, and cost.

## 구현 단계 제안

### Phase 1 - Track 1 objective extraction, cheap/high confidence

- Add path/op/scope instrumentation to every `read_deliverable` dispatch.
- Add `criterion_nature` to grade JSON using the Step 1 classifier.
- Expand XLSX formatting:
  - `number_format`
  - alignment/wrap
  - row heights
  - conditional formatting summary
  - freeze panes
  - protection/data validation
  - print area/page setup
- Add richer audio metrics on top of PyAV:
  - true clipping count
  - LUFS via `pyloudnorm`
  - silence spans
  - explicit codec/container metadata
- Add deterministic verdict helpers for explicit thresholds. Keep LLM as final arbiter only where needed.

This phase intentionally does not claim to solve the 140 overall-style critical items. It creates better supporting evidence and closes objective criteria.

### Phase 2 - Track 2 overall-style decomposition, medium/heavy

- Define the overall-style decomposition rule as a first-class recipe:
  - render integrity
  - layout consistency
  - readability
  - visual hierarchy
  - table/data legibility
  - professional finish
  - blocking defects
- Add judge-visible render snapshots for Office artifacts:
  - XLSX sheet renders
  - DOCX page renders
  - PPTX slide renders
  - PDF/image existing renders
- Add Office XML extraction for DOCX/PPTX/XLSX only as supporting evidence, not as the verdict mechanism:
  - font sizes
  - headings
  - tables
  - slide layout names
  - image counts/placements
  - margins/sections/page setup
- Build a gold set for overall-style first: all 140 if feasible, otherwise stratified sample before model selection.
- Calibrate pass/partial/fail thresholds against that gold set.

### Phase 3 - evidence bundling + reference comparison, heavy / owner-go

- Build task-level evidence bundle caching so each deliverable is read/rendered once per task, then sliced per criterion.
- Add evidence-family batching for multiple similar criteria, especially text/table criteria, to reduce cost without weakening evidence.
- Add reference-file namespace separation: deliverable paths vs reference paths must be explicit so the judge cannot silently grade the wrong file.
- Containerize the grading runtime and pin GHCR digest in workflow.
- Add OCR/layout analysis for rendered Office pages.
- Add reference-comparison lane:
  - workbook value joins
  - document text alignment
  - audio cross-correlation/DTW
  - visual side-by-side/reference image checks
- Run paired A+B validation with gold labels.

## 미결: reference-requiring criterion 처리

Reference-requiring is small but not ignorable:

- Overall: 203/10,453(1.9%)
- Critical: 12/483(2.5%)
- Audio critical reference: 4/17 audio critical items
- Formatting critical reference: 1/157 formatting critical items
- Text critical reference: 7/297 text critical items

Design stance:

- Do not let deliverable-only extraction decide these items.
- Mark them `needs_reference` and require explicit reference file availability.
- Use `RubricLoader.download_reference_files(task)` only in grading context, never candidate generation context.
- Keep reference evidence separated from deliverable evidence in paths and logs.
- If reference is unavailable, emit `judge_error` or conservative partial/fail depending on criterion sign and max score; do not hallucinate.

Reference comparison modules needed later:

| Reference type | Comparator |
|---|---|
| XLSX/workbook values | sheet/range matching, key joins, formula/value comparison |
| DOCX/PDF source docs | text extraction + section/field matching |
| Images/logos/floor layouts | render both sides, OCR/object matching, perceptual hash/vision judge |
| Audio stems/reference tracks | codec/fidelity probe, cross-correlation alignment, spectral/segment comparison |
| External truth/citations | URL reachability and source whitelist where rubric requires it |

## Decision for next owner step

Recommended next work is not "finish perception" in isolation. The highest-value next slice is:

1. path/op/scope instrumentation,
2. XLSX formatting v2 attributes,
3. rendered Office evidence design/prototype,
4. holistic formatting dimension rubric,
5. then paired mini-vs-standard measurement on fixed evidence.

This keeps the original goal intact: choose the cheapest grader that remains accurate and strict. But it moves the model decision after the evidence problem, where it belongs.
