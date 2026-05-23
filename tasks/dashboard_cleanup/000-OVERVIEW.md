# 000 — 문제 정의 + 컨셉 + 아키텍처

## 1. 배경

PR #46 (`feat(grading): Phase A wow — narrative + dashboard integration`,
2026-05-23 머지) 직후 `data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json`
이 dashboard에 노출되며 다음 misleading 발견:

- **inference 모델 vs judge 모델 혼동** — GradeDetail 헤더가 judge 모델로
  표시. 사용자는 "GPT-5.4-pro 가 직접 풀었다"고 오해.
- **dummy ↔ v1.0 혼재 신호 부정확** — Awaiting 배너가 v1.0 grade가 있어도
  dummy 하나 때문에 표시.
- **운영 health 메트릭 노출 부재** — `judge_error_rate=23.81%` 같은
  운영성 핵심 지표가 dashboard 어디에도 없음.

## 2. 컨셉 합의

### 2.1. Inference 와 Grading 은 별개 (Q1)

| 단계 | 모델 | 출처 |
|---|---|---|
| Inference | varies (gpt-5.2-chat, gpt-5.4, …) | `batch-runner/experiments/<exp>.yaml` `condition_a.model.deployment` |
| Grading | varies (gpt-5.4-pro, future: Claude/Gemini) | `grading_configs/*.yaml` `judge.model` |

Dashboard는 두 모델을 **분리해서** 노출. 단일 모델만 보이면 안 됨.

### 2.2. Grade 상태 머신 (Q2)

experiment 마다 정확히 3 상태:

```
NO_GRADE         — data/grades/<exp>__*.json 파일이 0개
LEGACY_DUMMY     — dummy_gpt5_baseline.json 만 존재 (schema_version 없음)
GRADED_V1        — schema_version=1.0 파일이 1개 이상 존재
```

`LEGACY_DUMMY` 와 `GRADED_V1` 이 동시 발현되면 → `GRADED_V1` 우선
(dummy 는 legacy demo로 별도 섹션 분리).

### 2.3. Judge multiplicity (Q3, future-proofing)

- 한 experiment에 여러 judge 의 grade 파일이 존재 가능 (Phase B).
- 1차에선 가장 최근 (mtime) v1.0 grade 를 메인으로 표시.
- "Other judges" 칩으로 다른 judge 결과도 접근 가능하게 (Phase B에서 확장).

### 2.4. Health 메트릭 노출 (Q4)

다음을 dashboard 1차 시민으로 노출:

| 메트릭 | 의미 | 경보 임계 |
|---|---|---|
| `summary.wow.judge_error_rate` | judge 호출 실패율 | > 5% 빨강 |
| `summary.wow.judge_pass_rate` | judge 항목 통과율 | — |
| `summary.wow.precheck_pass_rate` | precheck 항목 통과율 | — |
| `summary.cost.total_judge_calls` | 채점 비용 추정 | — |
| `summary.cost.total_judge_latency_sec` | 채점 소요 시간 | — |

### 2.5. Single-judge UI 정리 (Q5)

- `Grader Disagreement` 카드 — `inconsistent_grades > 0` 일 때만 표시
  (현재 single-judge면 항상 0). Phase B multi-judge 도입 후 의미.
- `disagreementData` 계산은 유지 (Phase B에서 재활용).

### 2.6. Copy 합의 (Q6)

- "self-assessed QA" 와 "LLM-judge grade" 가 **다른 것** 임을 매 카피마다
  명시. "(self-assessed, not the LLM-judge grade)" 같은 인라인 클러리피케이션
  적극 사용.
- Banner copy:
  - `GRADED_V1` 단독 → banner 없음
  - `LEGACY_DUMMY` 단독 → "Legacy demo grades — run grade-run.yml to get
    real LLM-judge scores."
  - `GRADED_V1` + `LEGACY_DUMMY` 혼재 → "Some experiments show legacy demo
    grades alongside fresh LLM-judge results."

## 3. 아키텍처

```
[grade JSON v1.0 (007 schema)]
   judge.model + inference_model + summary.wow.* + summary.cost.*
        │
        ▼ scripts/aggregate-grades.mjs (v1.0 분기)
   - explicit inference_model (no fallback to judge.model)
   - explicit grade_status: 'graded_v1' | 'legacy_dummy' | 'no_grade'
   - summary.wow / summary.cost 그대로 passthrough
        │
        ▼ public/generated/grades-index.json
        │
        ▼ src/hooks/useGrades.ts (typed)
        │
        ├──→ Dashboard/GradingAnalysisView
        │     - Status-aware banner
        │     - Health row (3 메트릭 + 2 cost)
        │     - Disagreement 카드는 inconsistent > 0 일 때만
        │
        ├──→ GradesSummary (cards)
        │     - LegacyBadge | WowBadge | NoGradeBadge
        │     - Inference vs Judge 분리 표시
        │
        └──→ GradeDetail
              - Header: "Inference: <m1> · Graded by <m2> · <N> tasks"
              - WOW section (변경 없음)
              - Health row 위 추가
```

## 4. PR 분할 (확정)

### Track 1 — 별도 핫픽스 PR (이 spec 외)
- `grading_configs/default_gpt5pro.yaml`: 800 → 1600 (truncation 가설)
- `batch-runner/step8_grade.py`: experiment yaml에서 `inference_model` 채우기

### PR #1 (이 spec 패키지, 001~005)
- 신규: 없음 (기존 컴포넌트 수정 위주)
- 수정:
  - `scripts/aggregate-grades.mjs` — `grade_status` 필드 추가, fallback 제거
  - `src/hooks/useGrades.ts` — `inference_model`, `grade_status`, `judge_model` 정확히 타입
  - `src/pages/GradeDetail.tsx` — header 모델 표시, Health row
  - `src/components/GradesSummary.tsx` — 카드 badge, inference/judge 분리
  - `src/components/dashboard/GradingAnalysisView.tsx` — banner 조건, 통계 row
  - `src/components/ScopeBadge.tsx` — `graded_v1` 상태 추가
  - `src/data/tooltipTexts.ts` — copy pass 2

## 5. 운영 정책

### 5.1. backward compat

- `dummy_gpt5_baseline.json` 은 `LEGACY_DUMMY` 상태로 영구 표시.
- 기존 `is_dummy` 필드는 유지 (테스트 호환). 새 `grade_status` 추가.

### 5.2. Phase B 대비

- `inconsistent_grades`, `Grader Disagreement` 로직 보존.
- Per-judge grade selector slot 마련 (UI 자체는 1차에 미구현, 1줄 주석으로
  TODO 표시).

## 6. WOW 메트릭 영향

PR #46 의 WOW 섹션 (W1~W6) 은 **무변경**. 본 spec은 surrounding chrome 정리
중심.

## 7. 비용 / 라이선스 / 가드

- 코드 변경만. 데이터 변경 없음.
- backward compat 보장.

## 8. 의사결정 박제

본 명세 패키지는 PR #1 머지 전까지 frozen. 변경 필요 시 amendment 후 사용자
승인.
