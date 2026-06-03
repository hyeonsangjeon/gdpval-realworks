# BUG2 — DELIVERABLE SELECTION

## 한 줄 결론

220개 exp003 task에서 reference 파일이 `deliverable_files/<task>/`에 echo된 task는 **113 / 220**이고, 그중 **62건**은 정렬/first-file 계열 로직이면 reference가 먼저 노출되는 고위험 케이스다. persisted grade JSON에는 실제로 judge가 연 `deliverable_path`가 저장되어 있지 않아서 220 전체의 historical reference 오채점 수와 false-low/false-high 방향은 복원할 수 없다. 다만 owner gold/HITL 표본에서는 **4건**이 실제 파일 오선택으로 확인됐고, 그중 reference 오선택 **3건**(`7d7fc9a7`, `43dc9778`, `ee09d943`) + supporting-file 오선택 **1건**(`99ac6944`)은 set-diff + 요청 확장자/primary-bundle 선택으로 **4/4 교정**된다. 방향은 gold에서 false-low 2건 이상(`7d7fc9a7`, `43dc9778`)과 false-high 1건(`ee09d943`)이 이미 확인됐고, `99ac6944`는 required PDF 대신 support xlsx를 본 파일형식 오선택이다.

## PHASE 1 — Bug2 범위

### 읽은 소스

- Task/result metadata: `batch-runner/results/exp003_GPT52Chat_baseline_runner_exec/report/report_data.json`
- Reference source of truth: `reference_file_urls` basename, URL-decoded. HF/local parquet `data/gdpval-local/data/train-00000-of-00001.parquet`에도 같은 reference 목록이 보존되어 있음.
- Candidate output list: `deliverable_files` from exp003 report metadata.
- Grade JSON audit: `data/grades/*`에는 task별 item grade/evidence는 있으나 judge가 실제로 고른 `deliverable_path` 필드는 없음. v2 tool JSON은 현재 10 task sample만 있고, full 220 historical file choice는 저장되지 않았음.
- Current v2 harness path: `batch-runner/core/grader.py`의 `_list_files()`가 deliverable directory의 모든 파일을 정렬해 넘기고, `_judge_via_tool_calling()`이 `file_names = [f.name for f in files]`를 그대로 judge prompt에 넣음. `batch-runner/prompts/grader_judge_v2.md`는 이 목록 전체를 “LLM under test produced these files”라고 부른다. 여기서 reference namespace가 사라진다.

### Metadata 집계

| metric | count | meaning |
|---|---:|---|
| total tasks | 220 | exp003 report rows |
| tasks with deliverable files | 219 | one task has no generated files |
| tasks with reference inputs | 125 | benchmark supplied input/reference files |
| tasks where reference basename appears inside `deliverable_files` | 113 | proven reference echo contamination surface |
| echo tasks that also have at least one new/generated candidate | 113 | reference and real output are mixed in same folder |
| tasks where first recorded deliverable file is a reference | 62 | high risk for first-file or list-order-biased selection |
| tasks with exactly one post-set-diff generated candidate | 140 | set-diff alone is decisive |
| tasks with multiple post-set-diff generated candidates | 79 | need extension/primary-bundle logic |
| tasks with zero generated candidates | 1 | should become absent/judge_error, not arbitrary reference selection |

The most important number is not just 62; it is that **113 tasks mix reference inputs and generated outputs in the same judge-visible namespace**. Even when the reference is not first, the judge can still choose it because the prompt labels every listed file as a produced deliverable.

### High-risk list: first file is reference (62)

`83d10b06`, `43dc9778`, `ee09d943`, `4b894ae3`, `05389f78`, `76d10872`, `dfb4e0cd`, `2ea2e5b5`, `a45bc83b`, `b7a5912e`, `aa071045`, `476db143`, `61f546a8`, `61717508`
`0ed38524`, `87da214f`, `ec2fccc9`, `8c8fc328`, `c94452e4`, `b78fd844`, `4520f882`, `0353ee0c`, `bf68f2ad`, `efca245f`, `211d0093`, `d4525420`, `cecac8f9`, `6436ff9e`
`3940b7e7`, `61b0946a`, `61e7b9c6`, `4b98ccce`, `6974adea`, `e6429658`, `b5d2e6f1`, `1137e2bb`, `57b2cdf2`, `84322284`, `a46d5cd2`, `b1a79ce1`, `e4f664ea`, `a079d38f`
`fd6129bd`, `ce864f41`, `58ac1cc5`, `1e5a1d7f`, `ed2bc14c`, `fd3ad420`, `0818571f`, `11593a50`, `90f37ff3`, `a73fbc98`, `7151c60a`, `90edba97`, `19403010`, `105f8ad0`
`bb863dd9`, `4de6a529`, `4c4dc603`, `552b7dd0`, `11dcc268`, `76418a2c`

### Full reference-echo list (113)

`83d10b06`, `7b08cd4d`, `7d7fc9a7`, `43dc9778`, `ee09d943`, `17111c03`, `c44e9b62`, `4b894ae3`, `24d1e93f`, `05389f78`, `85d95ce5`, `76d10872`, `dfb4e0cd`, `4c18ebae`
`2ea2e5b5`, `c357f0e2`, `a45bc83b`, `b7a5912e`, `aa071045`, `476db143`, `61f546a8`, `61717508`, `0ed38524`, `87da214f`, `d025a41c`, `3a4c347c`, `ec2fccc9`, `8c8fc328`
`e222075d`, `c94452e4`, `75401f7c`, `46b34f78`, `b78fd844`, `4520f882`, `3f821c2d`, `e996036e`, `6dcae3f5`, `1aecc095`, `0353ee0c`, `40a8c4b1`, `4d1a8410`, `bf68f2ad`
`efca245f`, `68d8d901`, `211d0093`, `d4525420`, `45c6237b`, `cecac8f9`, `6436ff9e`, `c6269101`, `be830ca0`, `46fc494e`, `3940b7e7`, `8077e700`, `5a2d70da`, `61b0946a`
`61e7b9c6`, `c9bf9801`, `6d2c8e55`, `4b98ccce`, `5d0feb24`, `6974adea`, `e6429658`, `b5d2e6f1`, `f841ddcf`, `47ef842d`, `1137e2bb`, `c3525d4d`, `c657103b`, `57b2cdf2`
`84322284`, `a46d5cd2`, `e14e32ba`, `b1a79ce1`, `e4f664ea`, `a079d38f`, `fd6129bd`, `ce864f41`, `58ac1cc5`, `3c19c6d1`, `55ddb773`, `1e5a1d7f`, `0419f1c3`, `ed2bc14c`
`fd3ad420`, `0818571f`, `6074bba3`, `11593a50`, `90f37ff3`, `d3d255b2`, `01d7e53e`, `a73fbc98`, `7151c60a`, `90edba97`, `f2986c1f`, `ffed32d8`, `a69be28f`, `788d2bc6`
`74ed1dc7`, `69a8ef86`, `d7cfae6f`, `19403010`, `7ed932dd`, `105f8ad0`, `15d37511`, `bb863dd9`, `fe0d3941`, `4de6a529`, `4c4dc603`, `bb499d9c`, `552b7dd0`, `11dcc268`
`76418a2c`

### Direction: what can and cannot be inferred

Metadata can prove whether a listed file is reference-vs-new. It **cannot** prove whether a wrong-file grade is false-low or false-high, because that requires looking at both the actual generated deliverable and the reference/support file quality. The owner gold examples prove the bug is bidirectional:

| task | wrong file class | observed direction / risk |
|---|---|---|
| `7d7fc9a7` | reference PDF selected instead of generated workbook | false-low pattern in owner note |
| `43dc9778` | reference W-2 PDF selected instead of generated 1040 draft PDF | false-low pattern in owner note |
| `99ac6944` | generated support xlsx selected instead of required single PDF | file-type/primary-target wrong; likely false-low for PDF-delivery criterion |
| `ee09d943` | reference dump selected instead of generated workbook | false-high pattern: reference looked polished/complete while generated workbook had `TO BE COMPLETED` |

So Bug2 is not a leniency-only bug and not a perception bug. It corrupts the input object the judge sees, and it can move scores both directions.

## PHASE 2 — 선택 로직

### Deterministic selector contract

The selector should run **before** any text/vision/audio judging and should produce two separate namespaces:

- `candidate_deliverables`: files the model generated and that may be graded as outputs.
- `reference_files`: input/reference files available only to criteria that explicitly require comparison against provided inputs.

Reference files must never be listed under “candidate deliverable files”. If a judge/tool asks to open a reference path while grading a deliverable-only criterion, the harness should reject or flag that call rather than silently grading the wrong object.

### Rule order

1. **Set-diff first.** Build normalized basenames from `reference_files` / `reference_file_urls`. Remove any `deliverable_files` entry whose basename matches a reference basename. This is the main fix and handles the three reference cases: `7d7fc9a7`, `43dc9778`, `ee09d943`.
2. **Zero candidate guard.** If set-diff leaves zero files, emit `judge_error: no_generated_deliverable_after_reference_diff` or `deliverable_absent_after_reference_filter`. Do not choose a reference as fallback.
3. **Single candidate fast path.** If one candidate remains, select it. This covers **140 / 220** tasks.
4. **Requested kind / rubric extension matching.** Use file-delivery criteria and task prompt wording such as “single PDF”, “Excel workbook”, “PowerPoint presentation”, “Word document”, plus explicit extensions/file names in rubric items. This fixes `99ac6944`: no references exist, but rubric/prompt require a single PDF, so `West_Coast_Tour_IEM_Mobile_Setup.pdf` wins over `IEM_Budget_Breakdown.xlsx` and PNG support files.
5. **Primary bundle for multi-deliverable tasks.** If the prompt/rubric requires multiple deliverables, the selector should return a bundle of primary deliverables, not invent one winner. Examples: `27e8912c` has a checklist PDF and action-items DOCX; `a74ead3b` has Session 13 and Session 14 PPTX files; `bbe0a93b` has three PDF documents. Generic criteria like “Overall formatting and style of the deliverable” should either judge/render the bundle or be split into per-deliverable items for gold/vision. Picking one arbitrary file is the old bug in a quieter coat.
6. **Deliverable Summary tie-break only.** If candidates remain tied, use Deliverable Summary only when the named file actually exists in the post-set-diff candidate set and matches the requested extension/kind. Do not use any self-assessed quality statement from the summary.
7. **Ambiguity guard.** If the selector cannot choose or bundle deterministically, emit `judge_error: ambiguous_deliverable_selection` with candidate/reference lists. Do not fall back to sorted first file.

### Pseudocode

```python
def select_deliverables(task_result, task_rubric, rubric_item):
    refs = normalized_basenames(task_result.reference_files or task_result.reference_file_urls)
    raw = task_result.deliverable_files
    generated = [p for p in raw if norm(basename(p)) not in refs]
    reference_echo = [p for p in raw if norm(basename(p)) in refs]

    if not generated:
        return Selection(error="no_generated_deliverable_after_reference_diff",
                         references=reference_echo)

    expected = infer_expected_outputs(task_rubric, rubric_item, task_result.instruction)
    # expected can include exact filenames, extensions, count, and whether the item is file-specific or task-level.

    if len(generated) == 1:
        return Selection(deliverables=generated, references=reference_echo, rule="set_diff_single")

    narrowed = match_expected_kind_and_filename(generated, expected)
    if expected.single_file and len(narrowed) == 1:
        return Selection(deliverables=narrowed, references=reference_echo, rule="kind_or_filename")

    if expected.multiple_primary_outputs:
        bundle = primary_outputs_only(generated, expected)
        if bundle:
            return Selection(deliverables=bundle, references=reference_echo, rule="primary_bundle")

    summary_hit = summary_named_file_tiebreak(generated, task_result.deliverable_summary, expected)
    if summary_hit:
        return Selection(deliverables=[summary_hit], references=reference_echo, rule="summary_tiebreak")

    return Selection(error="ambiguous_deliverable_selection",
                     candidates=generated,
                     references=reference_echo)
```

### Implementation insertion points

- `batch-runner/step8_grade.py::resolve_deliverable_dir()` can still find the directory, but it should not imply all files in that directory are deliverables.
- `batch-runner/core/grader.py::_judge_via_tool_calling()` currently passes all sorted names. Insert the selector before `file_names = ...`, then pass only selected candidate deliverable names to the judge.
- Tool prompt should show reference files in a separate section only when needed, e.g. “Reference input files (not candidate deliverables)”.
- Persist selector audit in grade JSON: `selected_deliverables`, `reference_files_excluded`, `selection_rule`, `selection_error`. Without this, future Bug2 diagnosis cannot recover exact historical file choice.

## PHASE 3 — gold/HITL 재선택 검증

Local repo-visible HITL sheet has **20 items** in `docs/human-in-the-loop/overall-style-gold-grading-sheet.html`. The owner prompt mentions 21 total gold samples; the 21st exported record is not present in the local sheet/file set I can read, so this validation uses the 20 locally available entries plus the four named Bug2 cases.

Current HITL selected path is wrong for **4 / 20** locally visible items. The proposed selector includes the owner-target file for **20 / 20** items. The four named Bug2 cases are corrected **4 / 4**. Multi-primary cases are deliberately returned as bundles rather than arbitrary single-file picks; that is not a grading answer, it is a guardrail against another version of Bug2.

| task | current HITL selected | proposed selector output | owner target | owner target included? | note |
|---|---|---|---|---|---|
| `83d10b06` | `Sample.xlsx` | single: `Sample.xlsx` | `Sample.xlsx` | yes | unchanged single candidate |
| `7b08cd4d` | `2024_Fall_Music_Tour_PnL_As_of_2024-12-31.xlsx` | single: `2024_Fall_Music_Tour_PnL_As_of_2024-12-31.xlsx` | `2024_Fall_Music_Tour_PnL_As_of_2024-12-31.xlsx` | yes | unchanged single candidate |
| `7d7fc9a7` | `Aurisic_Prepaid_Insurance.pdf` | single: `Aurisic_Prepaid_Amortization_Schedule_Through_Apr2025.xlsx` | `Aurisic_Prepaid_Amortization_Schedule_Through_Apr2025.xlsx` | yes | reference echo removed by set-diff |
| `43dc9778` | `LISA W2 COMPRESS MIDDLE SCHOOL edit.pdf` | single: `Smith_2024_Form_1040_Draft.pdf` | `Smith_2024_Form_1040_Draft.pdf` | yes | reference echo removed by set-diff |
| `ee09d943` | `Prof_Fee_Dump-1.xlsx` | single: `Aurisic_Financials_4-25-1.xlsx` | `Aurisic_Financials_4-25-1.xlsx` | yes | reference echo removed by set-diff |
| `27e8912c` | `Workstation_Ergonomics_Checklist.pdf` | bundle: `Workstation_Ergonomics_Checklist.pdf`, `Organizational_Ergonomic_Action_Items.docx` | `Workstation_Ergonomics_Checklist.pdf` | yes | multi-primary: judge/render must see bundle or split by deliverable |
| `99ac6944` | `IEM_Budget_Breakdown.xlsx` | single: `West_Coast_Tour_IEM_Mobile_Setup.pdf` | `West_Coast_Tour_IEM_Mobile_Setup.pdf` | yes | supporting xlsx -> required single PDF |
| `7bbfcfe9` | `SCRA_Compliance_Test_Questions.xlsx` | single: `SCRA_Compliance_Test_Questions.xlsx` | `SCRA_Compliance_Test_Questions.xlsx` | yes | unchanged single candidate |
| `f9a1c16c` | `Tour_Stage_Plot.pdf` | single: `Tour_Stage_Plot.pdf` | `Tour_Stage_Plot.pdf` | yes | unchanged single candidate |
| `bbe0a93b` | `Kent_County_Needs_Assessment_Espanol.pdf` | bundle: `Kent_County_Community_Resource_Guide.pdf`, `Kent_County_Needs_Assessment_English.pdf`, `Kent_County_Needs_Assessment_Espanol.pdf` | `Kent_County_Needs_Assessment_Espanol.pdf` | yes | multi-primary: judge/render must see bundle or split by deliverable |
| `85d95ce5` | `J.S..pdf` | single: `J.S..pdf` | `J.S..pdf` | yes | unchanged single candidate |
| `1b1ade2d` | `Revised_Sourcing_and_Nomination_Workflow_Lamp_Assemblies.docx` | single: `Revised_Sourcing_and_Nomination_Workflow_Lamp_Assemblies.docx` | `Revised_Sourcing_and_Nomination_Workflow_Lamp_Assemblies.docx` | yes | unchanged single candidate |
| `93b336f3` | `EV_Battery_Assembly_Localisation_Partnership_Proposal.docx` | single: `EV_Battery_Assembly_Localisation_Partnership_Proposal.docx` | `EV_Battery_Assembly_Localisation_Partnership_Proposal.docx` | yes | unchanged single candidate |
| `575f8679` | `Immigration_and_Family_Stress_Evaluation_Plan.docx` | single: `Immigration_and_Family_Stress_Evaluation_Plan.docx` | `Immigration_and_Family_Stress_Evaluation_Plan.docx` | yes | unchanged single candidate |
| `0419f1c3` | `Performance Improvement Plan – John Miller (07-13-2025).docx` | single: `Performance Improvement Plan – John Miller (07-13-2025).docx` | `Performance Improvement Plan – John Miller (07-13-2025).docx` | yes | unchanged single candidate |
| `6dcae3f5` | `Email_to_PD_Key_Indicator_Analysis.docx` | bundle: `Chief Key Indicator 5-Year.xlsx`, `Email_to_PD_Key_Indicator_Analysis.docx` | `Email_to_PD_Key_Indicator_Analysis.docx` | yes | multi-primary: judge/render must see bundle or split by deliverable |
| `a74ead3b` | `Session_14_Nurturing_Parenting_Recovery.pptx` | bundle: `Session_13_Nurturing_Parenting_Recovery.pptx`, `Session_14_Nurturing_Parenting_Recovery.pptx` | `Session_14_Nurturing_Parenting_Recovery.pptx` | yes | multi-primary: judge/render must see bundle or split by deliverable |
| `ec591973` | `Differentiated_Distribution_Strategy_Slide.pptx` | single: `Differentiated_Distribution_Strategy_Slide.pptx` | `Differentiated_Distribution_Strategy_Slide.pptx` | yes | unchanged single candidate |
| `9a0d8d36` | `ISO_vs_NQSO_Tax_Comparison.pptx` | single: `ISO_vs_NQSO_Tax_Comparison.pptx` | `ISO_vs_NQSO_Tax_Comparison.pptx` | yes | unchanged single candidate |
| `403b9234` | `Chamber_of_Commerce_Partnership_Proposal.pptx` | single: `Chamber_of_Commerce_Partnership_Proposal.pptx` | `Chamber_of_Commerce_Partnership_Proposal.pptx` | yes | unchanged single candidate |

### Positive controls

The single-primary positive controls remain stable: `7bbfcfe9`, `1b1ade2d`, `0419f1c3`, plus `83d10b06`, `7b08cd4d`, `f9a1c16c`, `85d95ce5`, `93b336f3`, `575f8679`, `ec591973`, `9a0d8d36`, and `403b9234` all select the same owner-target generated file.

For multi-primary positive controls (`27e8912c`, `bbe0a93b`, `6dcae3f5`, `a74ead3b`), the correct behavior is **not** “pick the same one file the old HITL card happened to show”. The correct behavior is to expose the full primary deliverable bundle or split the criterion. This avoids regressions while preventing silent support/reference selection.

### Machine-evidence implication

Existing v1/v2 evidence should be interpreted with selection uncertainty:

- `7d7fc9a7`: v2 evidence quoted low-level formatting fields (`fill`, `bold`, `border`) while owner says the visible selected object was a reference PDF. Either way, the file namespace was contaminated; post-fix evidence must quote the generated workbook only.
- `43dc9778`: v2 evidence only showed generic PDF font metadata, insufficient to prove it inspected the 1040 draft rather than a supplied tax source PDF. Post-fix candidate list should contain only `Smith_2024_Form_1040_Draft.pdf` for deliverable grading.
- `99ac6944`: v1 evidence referenced the IEM proposal, but the HITL selected path was `IEM_Budget_Breakdown.xlsx`. The selector should enforce the single-PDF requirement before any judge looks at formatting.
- `ee09d943`: v2 gave 5/5 using evidence from a workbook that matched reference-dump style/structure, while owner found the generated workbook was half-complete. This is the clearest false-high pattern.

## 다음: 올바른 파일 → 렌더+vision routing 전제

This fix comes before perception. After selection is fixed, visual criteria should render **the selected generated deliverable or primary bundle**, then route to vision/audio as needed. Rendering or perception on a reference/support file only makes the false confidence more expensive.

## 미결 / owner 결정

- Decide how aggregation treats `judge_error: ambiguous_deliverable_selection`: recommended is harness error / ungraded flag, not rubric fail, because it is an infrastructure selection failure.
- Decide whether generic “Overall formatting and style” on multi-deliverable tasks should grade a bundle in one call or be split into per-deliverable HITL/vision items.
- Add selected-file audit fields to grade JSON before the next run; otherwise future investigations will again have to infer from evidence and owner inspection.
- The 220-wide exact false-low/false-high count needs either persisted selected paths from a rerun or human/vision audit of selected-vs-true files. Metadata alone proves exposure, not score direction.
