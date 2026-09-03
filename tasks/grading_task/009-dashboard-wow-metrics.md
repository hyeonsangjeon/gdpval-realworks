# 009 — Dashboard WOW 메트릭 & UI 통합

> **PR 분할**: PR #2 (Phase A wow). PR #1엔 포함 X.

## 목적

007 schema의 풍부한 item-level 데이터를 활용해, OpenAI의 task-level binary
대비 “WOW”한 시각화를 제공. C2(카피 수정) 포함.

## 변경 파일

| 파일 | 변경 |
|---|---|
| `scripts/aggregate-grades.mjs` | 신규/수정 — 007 schema 파싱, WOW 메트릭 계산, generated JSON 생성 |
| `src/hooks/useGrades.ts` | 신규 메트릭 타입 export |
| `src/pages/GradeDetail.tsx` | WOW 카드/차트 추가, 카피 수정 |
| `src/components/GradesSummary.tsx` | 카드 수정 |
| `src/data/tooltipTexts.ts` | i 풍선 텍스트 (Q3) |
| `src/types/*.ts` | 신규 타입 (RubricItem, ItemGrade 등) |

## WOW 메트릭 카드 (W1~W7 풀)

### W1 — Rubric Item Coverage
- 카드 제목: "Rubric Item Coverage"
- 값: `summary.wow.rubric_item_coverage_avg * 100` % (예: 78.2%)
- 서브: "OpenAI's task-level binary captures only `{0, 33, 67, 100}%`. We
  score every rubric item — averaging 78.2% across ~6,600 items."
- i 풍선: "각 task의 rubric 항목 중 통과(pass) 비율의 평균. OpenAI는
  task-level 0/1만 노출했으나 우리는 item-level partial 채점 결과를
  활용함."

### W2 — Critical Item Pass Rate
- 카드 제목: "Critical Items (weight ≥ 3)"
- 값: `summary.wow.critical_item_pass_rate * 100` %
- 서브: "Pass rate for high-weight rubric items — the “must-have”
  requirements."
- i 풍선: "rubric 가중치가 3점 이상인 핵심 요구사항의 통과율. 작은
  formatting 항목보다 결정적 요건을 얼마나 충족했는지 보여줌."

> **2026-09-03 소유자 결정으로 위 W2 사양은 폐기되었습니다.** 위 문단은
> 당시 무엇을 만들었는지 남기기 위해 그대로 둡니다.
>
> 위 사양의 세 문장이 모두 사실과 달랐습니다. ① rubric에는 `required`
> 필드가 실제로 있고 220개 task의 10,453개 항목 **전부에서 null**이라,
> 이 항목들을 "must-have"로 지정한 것은 아무것도 없습니다. ②
> `core/grader.py`의 기준은 가중치 3점이 아니라 `abs(max_score) >= 4`
> 이고, 별도의 weight 필드가 아니라 배점의 절댓값을 봅니다. ③ 이 값이
> gold-ceiling 합격 게이트와 대시보드 대표 카드에 동시에 쓰이면서,
> 휴리스틱이 판정을 내리고 있었습니다.
>
> 바뀐 것: 이름은 `High-magnitude item pass rate (|max score| ≥ 4)`,
> 카드는 대표 행 아래 진단 영역으로 내려가고, 게이트에서 빠집니다.
> 분모를 함께 표시하며, 센 항목이 하나도 없어 분모가 0이면 `0%`가 아니라
> **"not recorded"** 로 표시합니다.
>
> 바뀌지 않은 것: `MAGNITUDE_THRESHOLD`는 4 그대로, `data/grades/**`의
> 어떤 payload도 다시 쓰지 않았고, JSON 키
> (`critical_item_pass_rate`, `critical_fail`, `item_counts.critical_items`)
> 도 발표된 이름을 그대로 씁니다.
>
> 근거와 실측 수치: `data/grades/_validation/REQUIRED_ITEM_DEFINITION.md`,
> 구현: `src/components/wow/HighMagnitudeItemCard.tsx`,
> 판정 규칙: `src/components/wow/highMagnitudeReading.ts`,
> 회귀 방지: `scripts/__tests__/high-magnitude-label.test.mjs`.

### W3 — Precheck vs Judge Breakdown
- 카드 제목: "Structure vs Reasoning"
- 두 바: precheck_pass_rate (e.g., 92%) vs judge_pass_rate (e.g., 64%)
- 인사이트 라벨: 격차가 크면 "Strong on structure, weak on reasoning" 등
- i 풍선: "결정론적 검증(파일 형식, 시트명 등)과 LLM 판단(내용 정확성)
  통과율을 분리. 모델이 형식은 따르나 내용 깊이가 부족한지 진단."

### W4 — Sector × Rubric Category Heatmap
- 형식: 11 sector × 3 category (file_structure / content_quality /
  domain_accuracy) heatmap
- 색상: pass_rate (0% red → 100% green)
- 데이터: `summary.wow.by_sector[*].pass_rate` per category
- i 풍선: "sector별로 어느 카테고리에서 실패가 많은지 패턴 시각화. 약점
  sector + 약점 카테고리 동시 식별 가능."

### W5 — Score Density Histogram (item-level)
- 차트: bar chart, 10개 bucket (0-10%, 10-20%, ..., 90-100%)
- 데이터: `summary.wow.score_density_histogram`
- 비교: OpenAI 더미는 4 bucket만 가능 (`0, 33, 67, 100`). 우리는 dense.
- i 풍선: "OpenAI 호스팅 채점은 task당 4단계 점수만 산출. 우리는 rubric
  item별 0~1 partial을 합산해 100단계 분포 가능."

### W6 — Rubric Severity Curve
- 차트: line chart, x=weight (1, 2, 3, 5, 8, ...), y=pass_rate
- 데이터: `summary.wow.rubric_severity_curve`
- 인사이트: sharp drop이 일어나는 weight 지점 = 모델 약점 임계
- i 풍선: "rubric 항목을 가중치별로 그룹화해 각 가중치의 통과율을 표시.
  특정 weight에서 급격히 통과율이 떨어지면 그 난이도가 모델의 임계점."

### W7 — Failure Mode Cluster (선택적, Phase A 후반부)
- 차트: bubble chart, x=sector, y=실패 패턴 클러스터, bubble size=빈도
- 데이터: judge evidence 텍스트를 LLM clustering (별도 batch 작업)
- **1차에선 빈 placeholder + "Coming soon" 배지로 두고 Phase A 후반부에
  채운다.** 이걸 위한 clustering 코드는 별도 spec 필요 (PR #2 미포함)

## OpenAI 호환 카드 (기존 dashboard 유지)

- Average Score (with CI) — `summary.openai_compat.avg_score_pct ± ci_pct`
- Perfect (100%) count
- Partial count
- Zero (0%) count
- (Inconsistent count는 Phase B multi-judge 도입 후 의미)

## C2 — 카피 수정

### `src/data/tooltipTexts.ts`
**기존**: "Tasks scored 100% by the external grading pipeline. The LLM
output fully met all rubric criteria."

**변경**: "Tasks scored 100% by the LLM-judge (rubric-based, automated).
The LLM output fully met all rubric criteria."

### `src/components/GradesSummary.tsx` & `src/pages/GradeDetail.tsx`
- "external grading pipeline" → "LLM-judge (rubric-based)"
- "grading result" → "LLM-judge grade" 또는 "rubric-based score"
- "official OpenAI grade" 같은 표현 모두 제거

### Dashboard 상단 배너 (현재 "Grading In Progress")
**기존**: "Some entries are placeholder data while we wait for the
external grading pipeline to finish."

**변경 조건부**:
- 실험에 `data/grades/<exp_id>__...json` 존재 → 배너 숨김
- 없으면: "Grading pending — run `grade-run.yml` for this experiment."

## aggregate-grades.mjs 동작

```javascript
// scripts/aggregate-grades.mjs
// Input:  data/grades/*.json (mix of dummy + v1.0)
// Output: public/generated/grades/<exp_id>.json
//         public/generated/grades-index.json
//
// 1. Glob data/grades/*.json
// 2. 각 파일 로드 + schema_version 분기
//    - is_dummy=true 또는 schema_version 없음 → legacy 패스
//    - schema_version="1.0" → 풀 변환
// 3. WOW 메트릭 추가 계산이 필요한 부분(e.g., precomputed가 없는 경우)
// 4. dashboard용 정규화 JSON 생성
// 5. 인덱스 파일 (exp_id 리스트 + metadata)
```

## 새 타입 (TS)

```typescript
// src/types/grade.ts
export type Verdict = 'pass' | 'partial' | 'fail' | 'judge_error'
export type DecidedBy = 'precheck' | 'judge'

export interface ItemGrade {
  rubric_item_id: string
  criterion: string
  max_score: number
  awarded_score: number
  verdict: Verdict
  decided_by: DecidedBy
  required: boolean | null
  evidence: string
  judge_confidence: number | null
  precheck_pattern_id: string | null
}

export interface TaskGrade {
  task_id: string
  sector: string
  occupation: string
  items: ItemGrade[]
  total_awarded: number
  total_max: number
  pct: number
  critical_fail: boolean
  judge_call_count: number
  precheck_count: number
  error: string | null
}

export interface GradeFile {
  schema_version: '1.0'
  experiment_id: string
  judge: { model: string; reasoning_effort: string; ... }
  rubric: { repo_id: string; short_sha: string; ... }
  prompt: { version: string }
  tasks: TaskGrade[]
  summary: {
    openai_compat: { avg_score_pct: number; ci_pct: number; ... }
    wow: { rubric_item_coverage_avg: number; ... }
    cost: { estimated_cost_usd: number; ... }
  }
}
```

## 새 페이지 라우트 / 컴포넌트 (제안, 1차에 일부만)

- `src/pages/GradeDetailV2.tsx` — schema v1.0 전용 풀 WOW 페이지
- `src/components/wow/WowCard.tsx` — W1~W4 카드 공통 컴포넌트
- `src/components/wow/SectorHeatmap.tsx` — W4 히트맵
- `src/components/wow/ScoreDensityHistogram.tsx` — W5
- `src/components/wow/RubricSeverityCurve.tsx` — W6

기존 `GradeDetail.tsx`는 legacy(dummy) 전용으로 유지하거나 v2로 흡수
(둘 다 그릴 수 있도록 prop으로 분기).

## 테스트 (Vitest 또는 manual)

- `aggregate-grades.test.mjs` — v1.0 파일 → 정규화 출력 정확성
- dashboard 시각적 회귀: smoke 데이터(exp998)로 화면 캡처

## 의존성

- 007 (schema)
- 008 (narrative와 동일 PR 또는 분리)
- 기존 dashboard 구조

## 비고

- W7 (Failure Mode Cluster)는 별도 LLM clustering batch가 필요해서
  Phase A 후반부 / Phase B 후보
- 차트 라이브러리는 기존 dashboard가 쓰는 것을 재활용 (recharts 또는
  유사). 신규 라이브러리 도입 지양
- "WOW" 라벨은 카드 헤더 위 작은 배지 또는 섹션 헤더로 표시 — 디자인은
  ui-designer agent에 위임 가능
