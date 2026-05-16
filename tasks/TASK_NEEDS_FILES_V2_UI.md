# TASK_NEEDS_FILES_V2_UI — Dashboard Dynamic Denominators + Stale Labels

> Policy V2 도입 시 stale 되는 `220` 매직넘버 7곳 + 보너스 발견 3건 fix.

## Goal
대시보드 UI 코드에서 task 분모 `220`을 runtime value 참조로 교체. stale label / chart clipping도 함께 fix.

핵심 불변식:
- 현재 표시 결과 동일 (default total_tasks=220에서 픽셀 단위 변화 0)
- 분모 변경 시 7곳 모두 일관되게 따라옴
- report_data.json 스키마는 안 건드림

## Scope
**수정**:
- src/pages/Dashboard.tsx (L170)
- src/data/tooltipTexts.ts (L6/14/20/57/71/75 + L8 sectors 자기모순)
- src/components/dashboard/TrendView.tsx (L117 Y domain)
- src/components/dashboard/LeaderboardView.tsx (L172/227/236 callsites + prop 받기)
- src/components/common/InfoTooltip.tsx, SectionHint.tsx, AboutModal.tsx (totalTasks 받아서 substituteTaskTotal 적용)
- 신규: src/lib/textFormat.ts (helper)

**손대지 않을 곳**: README, types/report.ts, useReports.ts, aggregate-*.mjs, ExperimentDetail/ErrorAnalysisView (이미 runtime), batch-runner/

## Design
### Phase 1: Helper + placeholder
src/data/tooltipTexts.ts 상단:
```ts
export const TASK_TOTAL_PLACEHOLDER = '{TASK_TOTAL}';
```
src/lib/textFormat.ts:
```ts
export function substituteTaskTotal(text: string, total: number): string {
  return text.replaceAll(TASK_TOTAL_PLACEHOLDER, String(total));
}
```
소비자(InfoTooltip/SectionHint/AboutModal)는 `totalTasks` prop 받아 helper 호출.

### Phase 2: Dashboard.tsx:170
```diff
- unit: 'of 220 tasks'
+ unit: `of ${displayExperiments[0]?.total_tasks ?? 220} tasks`
```

### Phase 3: TrendView Y domain
```diff
- <YAxis domain={[85, 100]} ... />
+ <YAxis domain={[Math.max(0, Math.floor(Math.min(...data.map(d => d.success_rate))/5)*5 - 5), 100]} ... />
```
빈 데이터 가드 추가: `data.length > 0 ? ... : [0, 100]`.

### Phase 4: tooltipTexts sectors
L8, L71 모두 "11 industry sectors" → "9 industry sectors".

### Phase 5: LeaderboardView prop drilling (REJECT 사유 반영)
`LeaderboardView.tsx`에 `totalTasks?: number` prop 추가. Dashboard.tsx가 `<LeaderboardView totalTasks={displayExperiments[0]?.total_tasks ?? 220} ...>` 전달. LeaderboardView 내 callsite 3곳(L~172 SectionHint, L~227 InfoTooltip experiment, L~236 InfoTooltip progress)에서 `substituteTaskTotal(text, totalTasks ?? 220)` 적용.

## Acceptance
- 모든 7개 `220` 위치 runtime-bound (LeaderboardView 3개 포함)
- substituteTaskTotal helper 사용
- L8 + L71 "9 industry sectors" 통일
- TrendView Y domain dynamic + 빈 데이터 가드
- npm run build 통과
- placeholder 토큰 dist 누출 0
- LeaderboardView.tsx RGB 식 외 task-count 220 잔존 0
- README/types/aggregator/batch-runner 무변경
- secrets 0

## Failure Policy
- 시각 회귀 발견 → REJECT, helper 적용 누락 점검
- placeholder 잔존 → REJECT, fallback 220 강제 적용 확인
- first-reviewer REJECT 1회 재시도
