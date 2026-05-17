# TASK_DOCS_CLEANUP — README sector/occupation consistency

## Goal
README들의 self-contradiction 정정. ground truth는 HF dataset(`openai/gdpval`,
split `train`, 220 rows) 라이브 카운트로 확인됨: **sectors = 9, occupations = 44**.
표기 패턴은 `src/data/tooltipTexts.ts`의 AboutModal 문구 스타일을 따른다
("N industry sectors and M occupations").

## Ground truth (HF dataset live count, verified this session)
- unique sectors = **9**
- unique occupations = **44**
- 표기: `9 industry sectors and 44 occupations`

## Scope
- `README.md` — L44 "across 11 sectors and 55 occupations" → ground truth로 정정
- `src/README.md` — L10 동일 정정

손대지 않을 곳:
- `src/data/tooltipTexts.ts` (UI PR에서 별도 처리 중 — scope 외)
- 코드 파일, `batch-runner/`, `tests/`
- README.md:261 / src/README.md:56 의 "9 sectors × N experiments" (이미 정확 — 유지)

## Acceptance
- 양 README에서 sector·occupation 카운트가 HF dataset 실제 값(9 / 44)과 일치
- 일관된 표기 (양 README 동일 문구)
- 코드 변경 0
- secrets 0
