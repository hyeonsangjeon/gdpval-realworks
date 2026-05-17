# TASK_STEP6_V2_FIELDS — Include v2 manifest fields in self_report.json

V2 시리즈 후속. `step6_report.py`가 self_report.json/report_data.json을 만들 때 BATCH PR이 도입한 v2 manifest 필드를 정식 포함.

## Goal
self_report.json 스키마에 v2 필드 추가:
- 각 task entry에: `prompt_classification`, `policy_results`, `has_deliverable_files`
- `_summary` 또는 `file_generation`에: `policy_counts`, `active_policy`, `confidence_distribution`

핵심 불변식:
- **default policy=deliverable_only에서 기존 필드 값 변화 0** (`needs_files_total`, `summary`, `sector_breakdown`, `task_results` 카운트 등)
- v1 manifest 환경에서도 backward-compatible: manifest에 v2 필드 없으면 self_report도 v2 필드 없이 생성 (또는 명시적 null/None)
- 추가 필드는 **append only**, 기존 키 0개 변경
- 다음 step6 실행이 v2 필드를 자동 생성하게 됨 → backfill 스크립트가 필요한 영구화 달성

## Scope
**수정**:
- `batch-runner/step6_report.py` (또는 `step3_compile_report.py` — `_build_report_data` 또는 동등 함수가 있는 곳)

**신규**:
- `batch-runner/tests/test_step6_v2_fields.py` — v2 manifest fixture로 self_report 생성 → v2 필드 포함 확인 + v1 manifest로도 backward-compat 확인

**손대지 않을 곳**:
- `batch-runner/core/*` (BATCH/GUARDRAILS에서 이미 끝남)
- `step0~5` (기존 파이프라인 무수정)
- `src/`, `scripts/aggregate-*.mjs` (PR A2가 처리)
- HF 업로드/다운로드 흐름

## Design

`step6_report.py`의 `_build_report_data` (또는 동등 함수)에서:
1. `NeedsFilesManifest` 로드 (이미 함)
2. **task_results** 빌드 시 각 task entry에 추가:
   ```python
   if manifest_v2_available(manifest):
       entry["prompt_classification"] = manifest.prompt_classification(task_id)
       entry["policy_results"] = {p: manifest.policy_result(task_id, p) for p in POLICIES}
       entry["has_deliverable_files"] = manifest.has_deliverable_files(task_id)
   ```
3. **`_summary` 또는 `file_generation`**에 추가:
   ```python
   if manifest_v2_available(manifest):
       summary["active_policy"] = manifest.summary.active_policy
       summary["policy_counts"] = manifest.summary.policy_counts
       summary["confidence_distribution"] = manifest.summary.confidence_distribution
   ```

`manifest_v2_available()` helper: manifest의 `_summary.active_policy`가 존재하면 v2로 판정 (v1 manifest는 None).

자세한 위치는 coder가 step6_report.py 코드 보고 가장 자연스러운 통합점 결정.

## Acceptance
- v2 manifest로 step6 실행 시 self_report.json에 신규 필드 모두 포함
- v1 manifest(단위 테스트에서 fixture로 생성)로 step6 실행 시 self_report.json에 신규 필드 부재 (또는 null) → backward-compat
- 기존 필드(`summary.needs_files_total`, `task_results` 카운트 등) 값 변화 0
- 단위 테스트 `test_step6_v2_fields.py` 통과
- BATCH/GUARDRAILS 회귀 테스트 (`test_prompt_classifier.py`, `test_resolve_needs_files.py`, `test_policy_guardrails.py`) 그대로 통과
- 변경 파일이 명시된 1개 수정 + 1개 신규 테스트 + spec = 3개
- secrets 0

## Failure Policy
- 기존 테스트 회귀 → REJECT, 수정 후 재시도
- first-reviewer REJECT 1회 재시도
- extreme-reasoner REJECT → 사용자 컨펌 필요

## Out of Scope
- 대시보드 표시 (PR A2)
- 과거 실험 backfill (A3)
- HF 업로드/다운로드 로직 변경
