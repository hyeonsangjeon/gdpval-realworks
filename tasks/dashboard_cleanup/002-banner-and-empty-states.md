# 002 — Awaiting 배너 조건 + dummy 정리

> **Amendments (post extreme-reasoner / ui-designer review)**:
> - `experiment_id` 를 aggregator의 1급 필드로 promote (startsWith 매칭의
>   brittleness 해소).
> - `no_grade` 배너 행은 unreachable (aggregator는 grade 파일이 있는 항목만
>   emit) — 표에서 제거.
> - `meta.report_scope` 와 grade-derived scope 의 **precedence 규칙**
>   명시: grade-derived가 wins, meta는 fallback. `'graded'` legacy 값을
>   union에 유지.
> - opacity 90% 대신 **muted/dashed border + DEMO badge** (ui-designer Q2).
> - amber → **neutral zinc** (legacy_only 배너), 혼재 시 **soft sky**
>   (ui-designer Q3).
> - GradesSummary 의 per-card "Disagreement" StatMini 도 조건부로 정리
>   (004 D2 와 정합).

## 목적

"Awaiting LLM-Judge Grade" 배너가 v1.0 grade가 이미 있는데도 떠 있어
사용자를 혼란시킴. dummy / v1.0 / no-grade 3 상태를 정확히 구분하고
배너 / 카드 시각을 그에 맞게 정리.

## 변경 파일

| 파일 | 변경 |
|---|---|
| `scripts/aggregate-grades.mjs` | `grade_status` + 1급 `experiment_id` 필드 추가 |
| `src/hooks/useGrades.ts` | `grade_status`, `experiment_id` 타입 추가 |
| `src/components/dashboard/GradingAnalysisView.tsx` | banner 재작성, dummy 카드 시각 |
| `src/components/GradesSummary.tsx` | DEMO badge, dashed border (opacity 제거) |
| `src/components/ScopeBadge.tsx` | `graded_v1`, `legacy_demo` 상태 + `'graded'` 유지 |
| `src/pages/ExperimentDetail.tsx` | `deriveScopeFromGrades` 도입, meta 와 merge |

## D1 — aggregate-grades.mjs

```js
function deriveGradeStatus(raw) {
  if (raw && raw.schema_version === '1.0') return 'graded_v1';
  if (raw && raw._meta && raw._meta.is_dummy) return 'legacy_dummy';
  return 'no_grade';
}
```

결과 객체에 다음 두 필드 항상 채우기:
- `grade_status: 'graded_v1' | 'legacy_dummy' | 'no_grade'`
- `experiment_id: string` — 1급 매칭 키. v1.0: `raw.experiment_id`
  fallback `basename` 에서 4-tuple 분해. legacy: `meta.experiment_id` 또는
  `basename`.

## D2 — Banner 조건 재작성 (unreachable row 제거)

```tsx
const statusCounts = useMemo(() => ({
  graded_v1: grades.filter(g => g.grade_status === 'graded_v1').length,
  legacy_dummy: grades.filter(g => g.grade_status === 'legacy_dummy').length,
}), [grades])

type BannerKind = 'none' | 'legacy_only' | 'mixed'
const bannerKind: BannerKind =
  statusCounts.legacy_dummy === 0 ? 'none'
  : statusCounts.graded_v1 === 0  ? 'legacy_only'
  :                                  'mixed'
```

배너 카피 / 색상 (ui-designer Q3):

| 상황 | 색 | 아이콘 | 카피 |
|---|---|---|---|
| `none` (graded_v1 만) | — | — | (배너 없음) |
| `legacy_only` | neutral zinc | `BookOpen` | "Showing legacy demo grades. Run `grade-run.yml` to get real LLM-judge scores." |
| `mixed` | soft sky | `Info` | "Some experiments still show legacy demo grades alongside fresh LLM-judge results." |

Tailwind:
```tsx
const BANNER = {
  legacy_only: 'bg-zinc-500/10 text-zinc-300 border-zinc-500/20',
  mixed:       'bg-sky-500/10  text-sky-300  border-sky-500/20',
}
```

amber 폐기 이유 — amber는 "주의/지연" 시그널. legacy demo data는 *category
label*이지 warning 이 아님. amber 재사용 시 retired "Awaiting" 배너와
동일한 오해 재발.

## D3 — Card 시각 분리 (opacity 제거)

### `legacy_dummy` 카드 (DEMO 라벨)
```tsx
// 카드 컨테이너
<Card className="bg-card/30 backdrop-blur border-border/60 border-dashed">

// 헤더 우상단 (WOW badge 와 동일 geometry, 중성 palette)
<span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md
                 bg-zinc-500/10 border border-zinc-500/30
                 text-[10px] font-bold uppercase tracking-wider text-zinc-400"
      title="Legacy demonstration data — not a real graded run">
  <BookOpen className="w-2.5 h-2.5" />
  DEMO
</span>
```

- 기존 `⏳ Awaiting LLM-Judge Grade` 줄은 **제거** (오해 유발)
- opacity 사용 안 함 → 텍스트 contrast 보존 (a11y)
- `border-dashed` 로 "이건 정식 grade 카드가 아님" 시그널 (WowEmptyState 와
  동일 vocab 재사용)
- 카드 내 `Disagreement` StatMini (`GradesSummary.tsx#L201-206`) 는
  `inconsistent_grades > 0` 일 때만 노출 (004 와 정합)

### `graded_v1` 카드
- 기존 WOW 뱃지 유지 (Sparkles + fuchsia gradient)
- 카드 헤더 우상단에 작은 "✓ v1.0 graded" 칩 (선택적, WOW 와 시각적
  중복 시 생략 가능)

## D4 — ScopeBadge.tsx + ExperimentDetail.tsx

```tsx
interface ScopeBadgeProps {
  scope: 'self_assessed_pre_grading'
       | 'graded'         // legacy meta value — backward compat
       | 'graded_v1'
       | 'legacy_demo'
}
```

`graded_v1` → fuchsia/violet (WOW signature)
`legacy_demo` → zinc + BookOpen
`graded` (legacy) → emerald (기존 그대로 유지)
`self_assessed_pre_grading` → 변경 없음 (기존 amber 유지 — 이 케이스만
"주의"/"대기" 시그널이 적합)

**Precedence** in `ExperimentDetail.tsx`:

```ts
function resolveScope(meta: ReportMeta, grades: GradeResult[]): ScopeBadgeProps['scope'] {
  // Grade-derived wins when an entry exists for this experiment.
  const match = grades.find(g => g.experiment_id === meta.experiment_id)
  if (match?.grade_status === 'graded_v1') return 'graded_v1'
  if (match?.grade_status === 'legacy_dummy') return 'legacy_demo'
  // No grade entry → fall back to meta.
  if (meta.report_scope === 'graded') return 'graded'
  return 'self_assessed_pre_grading'
}
```

`Dashboard.tsx` 의 demo mode 필터 (`meta.report_scope === 'self_assessed_pre_grading'`)
는 *unchanged* — meta-only 판단이며 grade 데이터를 보지 않음. (별도 변경
필요 시 future spec.)

## 테스트 (수동)

| 시나리오 | 기대 |
|---|---|
| 현재 (dummy + exp998 v1.0) | mixed sky banner, dummy 카드는 dashed border + DEMO badge, exp998 카드는 WOW + ✓ v1.0 graded |
| 모든 grade 삭제 | empty state ("No Grading Data Yet") 유지 |
| v1.0 만 (dummy 제거) | banner 없음, 카드만 깔끔 |
| dummy 만 | zinc legacy_only banner |

## 의존성

- 001 (inference vs judge 분리) — 같은 PR
- 003 (health row) — 같은 PR
- 004 (Disagreement guard) — 같은 PR (D3에서 cross-ref)

## 비고

- 배너 정책: severity ladder = neutral(info) < sky(info+) < amber(warning)
  < red(error). legacy demo는 카테고리 라벨이지 warning 이 아님.
- "Awaiting" 단어는 amber 단독 케이스에서 더 이상 안 씀.

