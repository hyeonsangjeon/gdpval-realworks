# DELIVERABLE SELECTOR — IMPLEMENTATION

## 한 줄 결론

selector 구현 완료. 브랜치: `feat/deliverable-selector` local only. Gold 20개 단위검증 **20/20** 정합, Bug2 4건 **4/4 교정**, positive control 회귀 **0**, wrong-format/ambiguous 7개는 **7/7 `wrong_format_primary`**로 분리 발화한다. 채점 파이프라인 통합, 재채점, Azure, vision 호출은 하지 않았다.

## 모듈

- `batch-runner/core/deliverable_selector.py`
- Selection 객체:
  - `SelectionTarget`: `target_id`, `paths`, `kind`, `role`, `evidence_rule`
  - `DeliverableSelection`: `selection_status`, `task_id`, `task_class`, `primary_targets[]`, `support_artifacts[]`, `reference_files_excluded[]`, `selection_rule`, `selection_error`
  - `CriterionTargetPlan`: criterion이 어느 target에 어떤 scope로 라우팅될지만 설명한다. 실제 verdict/score는 내지 않는다.
- Status:
  - `ok`
  - `selection_error`: 후보는 있으나 selector가 deterministic하게 못 고름. Harness/audit 문제로 ungraded/재시도 대상.
  - `no_generated_candidate`: reference set-diff 후 생성 후보 0. 모델 deliverable 실패.
  - `wrong_format_primary`: 생성 후보는 있으나 요청 primary 형식과 하나도 맞지 않음. 모델 deliverable 실패.

## 규칙 순서 구현

1. `reference_files` / `reference_file_urls` basename을 URL-decode + normalized set으로 만든다.
2. `deliverable_files - reference basenames`로 generated 후보와 `reference_files_excluded`를 분리한다.
3. generated 후보 0개면 `no_generated_candidate`; reference fallback 없음.
4. rubric/prompt/summary 텍스트에서 요청 primary 형식을 규칙 기반으로 추론한다: single PDF, Excel workbook, Word, PPTX, ZIP, WAV/audio, MP4/video, IPYNB.
5. 생성 후보가 있으나 요청 primary 형식과 하나도 맞지 않으면 `wrong_format_primary`.
6. 후보 1개면 `single_primary`.
7. 다중 후보는 hybrid class로 분기:
   - `main_plus_support`: primary 1개만 `primary_targets`, 나머지는 support.
   - `separate_equivalent`: document-like primary들을 split 대상 `primary_targets`로 반환, PNG 등은 support.
   - `format_variants`: rubric이 요구한 format을 primary로 선택.
   - deterministic 선택 불가 시 `selection_error`.
8. Deliverable Summary는 후보 동률 tie-break에만 쓰며, named file이 generated 후보에 존재하고 요청 확장자와 맞을 때만 사용한다. 품질 진술은 사용하지 않는다.

## criterion 라우팅 헬퍼

`plan_targets_for_criterion(selection, criterion)`를 추가했다.

- manifest/count/extension criterion → `target_scope="manifest"`
- file-specific criterion → inferred/named `file_target`
- cross-file consistency criterion → `primary_bundle`
- `main_plus_support` overall style → primary `file_target`
- `separate_equivalent` overall style → `split_children`, `aggregation_rule="blocking_min_else_mean"`
- non-ok selection → `selection_error`

## audit 스키마 정의

`ITEM_TARGET_AUDIT_SCHEMA`를 코드 안에 정의했다. 아직 grade JSON에 적용하지 않았다.

Required fields:

- `rubric_item_id`
- `target_scope`
- `target_ids`
- `child_grades`
- `aggregation_rule`
- `selected_paths`
- `support_paths_visible`

## 단위검증 결과

Command:

```bash
PYTHONPATH=batch-runner .venv/bin/python -m pytest batch-runner/tests/test_deliverable_selector.py -q
```

Result:

```text
7 passed in 1.56s
```

Coverage in tests:

- Gold 20 selector targets: **20/20**
- Bug2 4 cases:
  - `7d7fc9a7` → `Aurisic_Prepaid_Amortization_Schedule_Through_Apr2025.xlsx`
  - `43dc9778` → `Smith_2024_Form_1040_Draft.pdf`
  - `ee09d943` → `Aurisic_Financials_4-25-1.xlsx`
  - `99ac6944` → `West_Coast_Tour_IEM_Mobile_Setup.pdf`
- Multi-deliverable gold examples:
  - `27e8912c`: checklist PDF + action DOCX split, setup PNG support
  - `a74ead3b`: Session 13 + Session 14 PPTX split, background PNG support
  - `bbe0a93b`: English assessment + Spanish assessment + resource guide PDFs split
  - `6dcae3f5`: analytical workbook + email DOCX split, reference `Key Indicators.xlsx` excluded
- Wrong-format 7:
  - `ff85ee58`, `e222075d`, `c94452e4`, `75401f7c`, `a941b6d8`, `c7d83f01`, `a95a5829`
  - all return `wrong_format_primary`
- `no_generated_candidate` is separately tested and does not collapse into `selection_error`.
- Hybrid routing tested for manifest, file-specific, primary-bundle, and split overall-style scopes.

## 다음

Owner 리뷰 후 순서:

1. Pipeline 통합: `grader.py` / tool-calling prompt에 selected candidate namespace 적용.
2. Grade JSON audit 필드 적용: selected paths, excluded refs, target scope, child grades.
3. SP secret / artifact 인증 복구.
4. 재채점은 selector+audit 통합 후 **1회**.

이번 작업에서는 selector 로직 + 단위테스트만 수행했다.
