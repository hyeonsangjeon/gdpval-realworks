# Dashboard Cleanup — 명세 패키지

PR #2 (Phase A wow) 머지 직후 발견된 dashboard misleading 이슈와 운영 메트릭
누락을 정리하기 위한 spec 패키지.

## 한 줄 컨셉

> **dashboard가 "어떤 모델이 풀고, 어떤 judge가 채점했는지", "데이터가
> dummy/v1.0/legacy 중 어느 것인지", "judge 호출이 건강하게 끝났는지"를
> 1차 시민으로 명확히 보여주도록 정리.** 시각적 노이즈 (single-judge에서
> 의미 없는 disagreement 컴포넌트) 제거.

## 발견 경위

2026-05-23, PR #46 머지 직후 `data/grades/exp998_smoke_baseline_sample__*.json`
이 dashboard에 처음 v1.0 schema로 노출됨. 다음 misleading 발견:

1. GradeDetail 헤더의 모델명이 inference 모델이 아닌 **judge 모델** (gpt-5.4-pro)로
   표시됨. 실제 inference는 `gpt-5.2-chat`. 원인: aggregate-grades.mjs의
   `model = raw.inference_model || raw.judge.model` falsy fallback 때문에,
   `inference_model: ""` (download_inference_from_hf.py 의 빈 값) 가 judge로
   fallback.
2. "Awaiting LLM-Judge Grade" 배너가 v1.0 카드와 dummy 카드 **혼재 시에도**
   표시됨. 조건이 `grades.some(g => g.is_dummy)` 라서 v1.0 grade가 이미
   있어도 dummy 1개 때문에 배너가 뜸.
3. `Grader Disagreement` 컴포넌트가 single-judge 파이프라인에서도 노출됨.
   `inconsistent_grades`는 Phase B multi-judge에서만 의미.
4. dummy 카드와 v1.0 카드가 시각적으로 거의 동급. WOW 뱃지 외엔 구분 약함.
5. `judge_error_rate`, `judge_pass_rate`, `precheck_pass_rate` 같은 핵심
   운영 메트릭이 dashboard 어디에도 안 보임. 어제 smoke run의 23.8%
   judge_error를 모르고 Stage 2 trigger 했으면 그대로 220-task 결과가
   불량으로 채워질 위험.

## 명세 파일 인덱스

| # | 파일 | 대상 산출물 | PR |
|---|---|---|---|
| 000 | [000-OVERVIEW.md](000-OVERVIEW.md) | 문제 정의 + 컨셉 + 아키텍처 | — |
| 001 | [001-model-display.md](001-model-display.md) | inference vs judge 모델 분리 표시 | #1 |
| 002 | [002-banner-and-empty-states.md](002-banner-and-empty-states.md) | Awaiting 배너 조건, dummy 정리 정책 | #1 |
| 003 | [003-health-metrics.md](003-health-metrics.md) | judge_error_rate / judge_pass_rate / precheck_pass_rate 카드 | #1 |
| 004 | [004-disagreement-cleanup.md](004-disagreement-cleanup.md) | single-judge에서 의미 없는 UI 정리 | #1 |
| 005 | [005-copy-pass2.md](005-copy-pass2.md) | self-assessed vs LLM-judge 혼동 잡기 | #1 |
| 006 | [006-rollout.md](006-rollout.md) | PR 분할 + 검증 시퀀스 | — |

## PR 분할

- **Track 1 (별도 PR, dashboard_cleanup spec 외부)** — 핫픽스 2건
  - `grading_configs/default_gpt5pro.yaml`: `per_item_max_output_tokens` 800→1600
    (judge truncation 가설 검증)
  - `batch-runner/step8_grade.py`: experiment yaml에서 `inference_model`을
    실제로 채우기 (`condition_a.model.deployment`)
- **PR #1 (이 spec 패키지)** — 001~005 일괄
  - Dashboard misleading 정리. backward compatible (legacy dummy 표시 유지).
  - 회귀 테스트: `dummy_gpt5_baseline.json` 이 여전히 legacy 모드로 표시.

## 핵심 사실 (이 spec 패키지의 전제)

1. Inference 와 grading 은 **분리된 두 파이프라인 + 별개 모델**이다.
   - Inference: `batch-runner/experiments/<exp>.yaml` 의
     `condition_a.model.deployment` (예: `gpt-5.2-chat`, `gpt-5.4`)
   - Grading: `batch-runner/grading_configs/*.yaml` 의 `judge.model`
     (현재 모두 `gpt-5.4-pro`)
2. 같은 experiment에 대해 **여러 judge** 로 채점한 v1.0 grade 파일이
   존재할 수 있다 (파일명 4-tuple: `<exp>__<judge>__<rubric_sha>__<v>.json`).
   Phase B에서 cross-family calibration 도입 시 이게 빈번해짐.
3. `dummy_gpt5_baseline.json` 은 OpenAI 호스팅 채점 데모 자료. 영구
   보존하되 "legacy demo" 로 라벨링.
4. `schema_version === '1.0'` v1.0 grade 가 1개 이상 있는 experiment 는
   "graded" 상태. v1.0 grade 가 0개면 "pending" (dummy 가 있어도 pending
   취급).

## Quick start (개발자용)

```bash
# 명세 확인 후 작업 (PR #1 단일 PR)
git checkout -b feat/dashboard-cleanup

# 구현 후 빌드 검증
npm run aggregate && npm run build

# 회귀: dummy 가 여전히 legacy 모드로 표시되는지
node -e 'console.log(require("./public/generated/grades-index.json").map(g=>({id:g.id,sv:g.schema_version,is_dummy:g.is_dummy})))'

# 시각 검증
npm run dev
# → /grades/exp998_smoke_baseline_sample__... 페이지 확인
# → "Inference: gpt-5.2-chat · Graded by gpt-5.4-pro · 3 tasks" 표기 확인
# → /  (Dashboard) → Grading Analysis 탭에서 Awaiting 배너가 v1.0 grade 카드와
#                    혼재 시 사라지는지 확인
```
