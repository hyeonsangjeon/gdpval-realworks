# 207 — Legacy Removal

> PR2 / 8 of 9. Depends on 203-206 ToolCallingJudge stable.

## 목적

ToolCallingJudge가 정상 작동 확인 후, 사전 text 추출 + tier 분기 코드 일괄 삭제.

## 삭제 대상

1. `core/grader.py`:
   - `Judge` 클래스의 `deliverable_extract_max_chars` 호출 경로
   - `BatchJudge` (별 사용처 없으면)
   - `_build_tier_judges`, `tier_pro`/`tier_standard`/`tier_mini` 분기
   - `required is True` OR-가지 잔재 (101에서 시작, 여기서 마무리)
   - raw `verdict == "pass"` 직접 사용처 (100에서 시작, 여기서 마무리)

2. `core/grader.py` 또는 인근:
   - `_extract_deliverable_text` 또는 동등 함수
   - 1500자 truncation 관련 코드

3. `grading_configs/`:
   - `validation_hybrid.yaml`, `tiered_critical_pro_mini.yaml`, `validation_pro_only.yaml` → archive 폴더로 이동 (`grading_configs/_archive_v1/`)
   - 새 `default_v2.yaml` 생성 (208)
   - `_sweep_template.yaml`은 v1 sweep 재현용으로 유지하되 deprecated 마킹

4. tests:
   - `test_grader_routing.py` 중 tier 관련 케이스 삭제 또는 archive 표시
   - `test_grader_batch.py` 사용처 검토

## Acceptance

- `grep -r "tier_pro\|tier_standard\|tier_mini\|deliverable_extract_max_chars" batch-runner/core/ batch-runner/grading_configs/` → 0 matches
- 기존 v1 grade JSON 재생산 불가 (의도된 deprecation) — 단 backfill 스크립트로는 가능
- pytest 전체 green
