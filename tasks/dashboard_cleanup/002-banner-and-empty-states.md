# 002 — Awaiting 배너 조건 + dummy 정리

## 목적

"Awaiting LLM-Judge Grade" 배너가 v1.0 grade가 이미 있는데도 떠 있어
사용자를 혼란시킴. dummy / v1.0 / no-grade 3 상태를 정확히 구분하고
배너 / 카드 시각을 그에 맞게 정리.

## 변경 파일

| 파일 | 변경 |
|---|---|
| `scripts/aggregate-grades.mjs` | `grade_status: 'graded_v1' \| 'legacy_dummy' \| 'no_grade'` 필드 추가 |
| `src/hooks/useGrades.ts` | `grade_status` 타입 추가 |
| `src/components/dashboard/GradingAnalysisView.tsx` | banner 조건 재작성 + dummy 카드 시각 다운그레이드 |
| `src/components/GradesSummary.tsx` | dummy/v1.0/no-grade 배지 + 카드 스타일 분리 |

## D1 — aggregate-grades.mjs

```js
function deriveGradeStatus(raw) {
  if (raw && raw.schema_version === '1.0') return 'graded_v1';
  if (raw && raw._meta && raw._meta.is_dummy) return 'legacy_dummy';
  return 'no_grade';
}
```

결과 객체에 `grade_status` 필드 항상 채우기.

## D2 — Banner 조건 재작성

```tsx
const statusCounts = useMemo(() => ({
  graded_v1: grades.filter(g => g.grade_status === 'graded_v1').length,
  legacy_dummy: grades.filter(g => g.grade_status === 'legacy_dummy').length,
  no_grade: grades.filter(g => g.grade_status === 'no_grade').length,
}), [grades])

const showLegacyBanner = statusCounts.legacy_dummy > 0
const showMixedBanner = statusCounts.graded_v1 > 0 && statusCounts.legacy_dummy > 0
```

배너 카피:

| 상황 | 배너 |
|---|---|
| `graded_v1` 만 ≥ 1 | (배너 없음, clean state) |
| `legacy_dummy` 만 (graded_v1 = 0) | amber: "Legacy demo grades shown. Run `grade-run.yml` for any experiment to populate real LLM-judge scores." |
| `legacy_dummy` + `graded_v1` 혼재 | blue: "Some experiments show legacy demo grades alongside fresh LLM-judge results. Look for the WOW badge to identify graded-v1 results." |
| `no_grade` 만 | 이미 처리된 empty state (그대로) |

## D3 — Card 시각 분리

### `legacy_dummy` 카드
- 좌상단 작은 회색 "LEGACY DEMO" 라벨 (기존 amber dummy 라벨 대신)
- card opacity 90% 로 약간 톤다운
- title 옆 "📚" 또는 책 아이콘으로 demo 컨텍스트 강조
- 기존 `⏳ Awaiting LLM-Judge Grade` 줄은 **제거** (오해 유발)

### `graded_v1` 카드
- 기존 WOW 뱃지 유지 (W badge)
- 카드 헤더 우상단에 작은 "✓ v1.0 graded" 칩

### `no_grade` 카드 (현재 없지만 미래 대비)
- 회색 톤 카드 + "Pending — run grade-run.yml" 헬프

## D4 — ScopeBadge.tsx 확장

```tsx
interface ScopeBadgeProps {
  scope: 'self_assessed_pre_grading' | 'graded' | 'graded_v1' | 'legacy_demo'
}
```

`graded_v1` → 보라/그린 emphasis ("✨ LLM-Judge Graded (v1.0)")
`legacy_demo` → 회색 톤 ("📚 Legacy Demo")

ExperimentDetail 의 `report_scope` 매핑은 다음:

```ts
function deriveScopeFromGrades(experimentId: string, grades: GradeResult[]): ScopeBadgeProps['scope'] {
  const match = grades.find(g => g.label === experimentId || g.id.startsWith(experimentId))
  if (match?.grade_status === 'graded_v1') return 'graded_v1'
  if (match?.grade_status === 'legacy_dummy') return 'legacy_demo'
  return 'self_assessed_pre_grading'
}
```

ExperimentDetail.tsx 에서 이 헬퍼 사용.

## 테스트 (수동)

| 시나리오 | 기대 |
|---|---|
| 현재 (dummy + exp998 v1.0) | mixed banner blue, dummy 카드는 톤다운, exp998 카드는 WOW + ✓ v1.0 graded |
| 모든 grade 삭제 | empty state ("No Grading Data Yet") 유지 |
| v1.0 만 (dummy 제거) | banner 없음, 카드만 깔끔 |
| dummy 만 | amber legacy banner |

## 의존성

- 001 (inference vs judge 분리) — 같은 PR
- 003 (health row) — 같은 PR

## 비고

- 배너 색상은 amber → blue (mixed 경우) 로 의도적 변경. amber 는 "주의"
  뉘앙스가 강해 v1.0 grade 가 있는데도 띄우면 잘못된 신호.
- "Awaiting" 단어는 amber 단독 케이스에서만 유지하지 않고, 카피를
  "Legacy demo …" 로 명확히 바꿈.
