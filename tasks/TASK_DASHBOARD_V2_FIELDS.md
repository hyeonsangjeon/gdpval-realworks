# TASK_DASHBOARD_V2_FIELDS — Dashboard surfaces v2 manifest fields

A1(step6 v2 확장)의 sister PR. self_report.json에 v2 필드가 추가됐을 때 대시보드가 그것을 읽고 표시. v1 self_report(필드 없음)에서도 graceful fallback.

## Goal
다음 v2 필드를 대시보드 UI에 노출:
- 각 task의 `prompt_classification` (requires_file / explicit_exts / inferred_exts / confidence)
- 각 task의 `policy_results` (4 policies)
- 각 task의 `has_deliverable_files`
- summary 레벨: `active_policy`, `policy_counts`, `confidence_distribution`

핵심 불변식:
- v1 self_report(필드 없음)에서 정상 렌더 (에러 0, fallback graceful)
- v2 필드가 있을 때만 새 UI surface 표시
- 기존 UI 요소(KPI cards, Leaderboard, Heatmap 등) 픽셀 단위 변화 0 (v2 필드 없는 상태에서)

## Scope
**수정/신규**:
- `src/types/report.ts` — v2 필드 타입 추가 (모두 optional)
- `scripts/aggregate-reports.mjs` — 신규 필드 pass-through (필요 시)
- 신규 컴포넌트 또는 기존 컴포넌트 확장:
  - `ExperimentDetail` 페이지에 "Policy Comparison" 섹션 — 4 정책별 needs_files count 비교
  - "Confidence Distribution" mini-chart — explicit/inferred/ambiguous/text_only 분포
  - task table에 `confidence` 컬럼 또는 badge (옵션, coder 판단)

**손대지 않을 곳**:
- `batch-runner/` (A1이 처리)
- 기존 KPI cards / Leaderboard / Heatmap 동작 (회귀 0)

## Design

### 1. types/report.ts
optional 필드 추가:
```ts
export interface TaskResult {
  // ... existing fields
  prompt_classification?: PromptClassification | null;
  policy_results?: Record<string, boolean> | null;
  has_deliverable_files?: boolean | null;
}

export interface PromptClassification {
  requires_file: boolean;
  explicit_exts: string[];
  inferred_exts: string[];
  confidence: "explicit" | "inferred" | "ambiguous" | "text_only";
}

export interface ReportSummary {
  // ... existing
  active_policy?: string | null;
  policy_counts?: Record<string, number> | null;
  confidence_distribution?: Record<string, number> | null;
}
```

### 2. ExperimentDetail Policy Comparison 섹션
`src/pages/ExperimentDetail.tsx`에서 `summary.policy_counts`가 있으면 표시:
```tsx
{summary.policy_counts && (
  <Card>
    <CardHeader>Policy Comparison</CardHeader>
    <CardContent>
      Table or bar chart: 4 policies × count + delta from active_policy
    </CardContent>
  </Card>
)}
```

### 3. Confidence Distribution
`summary.confidence_distribution`가 있으면 stacked bar 또는 pie chart로 분포 표시.

### 4. aggregate-reports.mjs
신규 필드를 reports-index에 포함 (필요 시). v1 데이터는 필드 없이 통과.

## Acceptance
- types/report.ts 신규 optional 필드 추가
- v1 self_report에서 정상 렌더 (Console 에러 0, 신규 섹션은 conditional 미표시)
- v2 self_report에서 신규 섹션(Policy Comparison + Confidence Distribution) 표시
- `npm run build` 통과
- 기존 KPI/Leaderboard/Heatmap 시각 회귀 0 (v1 fixture로 확인)
- 변경 파일: types/report.ts + ExperimentDetail.tsx + (optional) aggregate-reports.mjs + 신규 컴포넌트 + spec = 5~6개 예상
- secrets 0

## Failure Policy
- v1 fallback에서 렌더 에러 → REJECT, optional chaining 점검
- npm build fail → REJECT
- first-reviewer REJECT 1회 재시도

## Out of Scope
- step6 확장 (A1)
- 과거 실험 backfill (A3, A1+A2 머지 후)
- HF 업로드/다운로드 흐름
