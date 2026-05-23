# 004 — Single-judge에서 의미 없는 UI 정리

> **Amendments (post extreme-reasoner review)**:
> - GradesSummary.tsx 의 per-card "Disagreement" StatMini 도 조건부로 정리.
>   GradingAnalysisView 차트뿐 아니라 카드도 같이 가야 의도가 일관됨.
> - Phase B 전환 시 whiplash 최소화: 카드 진입 시 footer 라벨로 "Multi-
>   judge mode" 명시.

## 목적

`Grader Disagreement` 컴포넌트가 single-judge 파이프라인 (현재 모든 v1.0
grade) 에서 `0 / N (0%)` 로 항상 0 표시. Phase B multi-judge 도입 전엔
시각 노이즈. 단, 미래 호환을 위해 로직은 보존.

## 변경 방침

| 정책 | 결정 |
|---|---|
| 컴포넌트 삭제 | ❌ (Phase B에서 재활용) |
| 데이터 계산 삭제 | ❌ (aggregate 단계 보존) |
| **조건부 렌더링** | ✅ `disagreementData.some(d => d.inconsistent > 0)` 일 때만 |
| GradesSummary card 의 Disagreement StatMini | ✅ `s.inconsistent_grades > 0` 일 때만 |
| 빈 상태 placeholder | ❌ (단일 judge에선 매뉴얼 정보가 더 혼란) |

## 변경 파일

| 파일 | 변경 |
|---|---|
| `src/components/dashboard/GradingAnalysisView.tsx` | `Grader Disagreement` 섹션 조건부 |
| `src/components/GradesSummary.tsx` | per-card Disagreement StatMini 조건부 |
| `src/data/tooltipTexts.ts` | `grading.graderDisagreement` copy 정리 |

## D1 — Disagreement section guard (GradingAnalysisView)

기존:
```tsx
{/* ─── 3. Grader Disagreement ─── */}
<div className="...">
  <h3>Grader Disagreement <InfoTooltip ... /></h3>
  {disagreementData.length > 0 ? (
    ...
  ) : (
    <p>No data</p>
  )}
</div>
```

변경:
```tsx
const hasDisagreement = disagreementData.some(d => d.inconsistent > 0)

{hasDisagreement && (
  <div className="...">
    <h3>Grader Disagreement <InfoTooltip ... /></h3>
    <ul>
      {disagreementData
        .filter(d => d.inconsistent > 0)
        .map(d => (...))}
    </ul>
    <p className="text-[10px] text-muted-foreground mt-2">
      Visible only in multi-judge mode (Phase B). Single-judge runs always show 0.
    </p>
  </div>
)}
```

## D2 — GradesSummary.tsx per-card guard

`GradesSummary.tsx#L201-206` 의 `StatMini label="Disagreement" value={s.inconsistent_grades}`
를 다음과 같이 조건부:

```tsx
{s.inconsistent_grades > 0 && (
  <StatMini
    icon={AlertCircle}
    label="Disagreement"
    value={s.inconsistent_grades}
    color="text-purple-400"
  />
)}
```

Single-judge 케이스에선 stat tile 자체가 사라짐. multi-judge 시 자동 등장.

## D3 — Tooltip copy 정리

`grading.graderDisagreement`:
```
"Cases where multiple judges scored the same task differently. Visible
 only in multi-judge mode (Phase B). High rates may indicate ambiguous
 rubric criteria."
```

## D4 — aggregate-grades / useGrades 계산 보존

`inconsistent_grades` 필드 계산 로직 (현재 single-judge면 항상 0) 은 그대로
둠. 단, JSDoc 코멘트 한 줄 추가:

```js
/**
 * inconsistent_grades: count of tasks where multiple judges produced
 * different scores. Always 0 for single-judge runs (Phase A). Populated
 * by Phase B multi-judge aggregator.
 */
```

## 회귀 테스트

- 현재 데이터(single-judge)에서 "Grader Disagreement" 섹션과
  per-card "Disagreement" StatMini 가 **모두 사라지는지** 확인.
- GradesSummary 카드 layout 이 stat 1개 빈 슬롯 없이 자연스러운지 확인
  (grid auto-fill 또는 flex 로 reflow 되어야 함).
- 가상 multi-judge fixture (inconsistent > 0) 만들어 섹션이 다시 나오는지
  확인 (단위 테스트 또는 dev 콘솔에서 hand-craft).

## 의존성

- 002 (grade_status) — 의존 X (별개)
- Phase B multi-judge spec — 본 spec과 무관, 미래 호환만 보존

## 비고

- 추후 multi-judge 도입 시 본 컴포넌트가 자동으로 다시 노출됨.
- "graderDisagreement" 라는 단어 자체는 보존 — Phase B 컨셉과 일치.
- Persistent placeholder (예: "Multi-judge mode not enabled") 는 의도적
  으로 안 둠 — dead chrome 양산.

