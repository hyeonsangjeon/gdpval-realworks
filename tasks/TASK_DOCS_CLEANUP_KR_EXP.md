# TASK_DOCS_CLEANUP_KR_EXP — KR README + Experiment Specs 9/44 통일

PR #30 (EN README 정정)의 후속. 동일 ground truth(9 sectors / 44 occupations / 220 tasks)로 잔존 위치 모두 fix.

## Goal
레포 내 "11 sectors / 55 occupations" 잔존 표기를 전부 9/44로 통일.

## Ground truth (재검증 완료)
- HF dataset 실측: distinct sectors = 9, distinct occupations = 44
- OpenAI 공식 dataset card: "220 real-world knowledge tasks across 44 occupations"
- 레포 audit 문서들도 9/44 ground truth로 결론

## Scope
**수정 대상**:
- `README_KR.md` — "11개 산업, 55개 직종" → "9개 산업, 44개 직종" (L44 부근 외에도 grep으로 모두 찾기)
- `src/README_KR.md` — 동일
- `docs/experiments/EXP013-016_SPECIFICATION.md` — 11/55 → 9/44
- `docs/experiments/EXP017-020_SPECIFICATION.md` — 동일
- `docs/experiments/EXP021-024_SPECIFICATION.md` — 동일
- 추가로 `grep -rn "11 sector\|11 industries\|11개 산업\|55 occupation\|55개 직종" --include="*.md"` 결과 중 미처리 위치 있으면 같이 처리 (단, `tasks/*REPORT.md`, `tasks/*AUDIT.md`는 historical record이므로 미수정)

**손대지 않을 곳**:
- `README.md`, `src/README.md` (PR #30이 이미 처리)
- `src/data/tooltipTexts.ts` (UI PR `feature/needs-files-v2-ui-v2`가 이미 처리)
- `tasks/HF_PROMPT_ANALYSIS_REPORT.md`, `tasks/DASHBOARD_UI_COUNT_AUDIT.md` (audit historical records)
- 코드 파일 전체
- batch-runner/

## Acceptance
- 위 명시 파일에서 11/55 잔존 0
- 9/44가 자연스러운 한국어/영문 표현으로 들어감
- 코드 변경 0
- secrets 0
