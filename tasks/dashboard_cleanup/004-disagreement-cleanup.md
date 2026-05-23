# 004 — Single-judge에서 의미 없는 UI 정리

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
| 빈 상태 placeholder | ❌ (단일 judge에선 메뉴얼 정보가 더 혼란) |

## 변경 파일

| 파일 | 변경 |
|---|---|
| `src/components/dashboard/GradingAnalysisView.tsx` | `Grader Disagreement` 섹션 조건부 |
| `src/data/tooltipTexts.ts` | `grading.graderDisagreement` copy 정리 |

## D1 — Disagreement section guard

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
      Visible only when multiple judges scored the same task (Phase B).
    </p>
  </div>
)}
```

## D2 — Tooltip copy 정리

`grading.graderDisagreement`:
```
"Cases where multiple judges scored the same task differently. Visible
 only when a Phase B multi-judge run is present. High rates may indicate
 ambiguous rubric criteria."
```

## D3 — useGrades / aggregate-grades 계산 보존

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

- 현재 데이터(single-judge)에서 "Grader Disagreement" 섹션이 **사라지는지** 확인.
- 가상 multi-judge fixture (inconsistent > 0) 만들어 섹션이 다시 나오는지
  확인 (단위 테스트 또는 dev 콘솔에서 hand-craft).

## 의존성

- 002 (grade_status) — 의존 X (별개)
- Phase B multi-judge spec — 본 spec과 무관, 미래 호환만 보존

## 비고

- 추후 multi-judge 도입 시 본 컴포넌트가 자동으로 다시 노출됨.
- "graderDisagreement" 라는 단어 자체는 보존 — Phase B 컨셉과 일치.
