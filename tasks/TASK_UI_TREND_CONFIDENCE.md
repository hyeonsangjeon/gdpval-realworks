# TASK_UI_TREND_CONFIDENCE — TrendView QA Axis + CONFIDENCE Banner Docs Cleanup

UI PR(feature/needs-files-v2-ui-v2) 후속. `DASHBOARD_UI_COUNT_AUDIT.md`가 잡은 두 MINOR 항목 처리.

## Goal
1. **TrendView.tsx QA Score Y축** `domain={[4, 7]}` 하드코딩 → dynamic (Success Rate 축이 v2-ui-v2에서 dynamic으로 바뀐 것과 동일 패턴)
2. **CONFIDENCE banner README drift 정정** — analyzer 조사 결과 컴포넌트 미구현 확정. README 4곳을 실제 동작 설명으로 정정 (Exception Type Distribution 차트 + AI Failure Insights 내러티브 기반)

## Scope
**수정 대상**:
- `src/components/dashboard/TrendView.tsx` — QA Y축 dynamic + 빈 데이터 가드
- `README.md` (L263) — CONFIDENCE NameError tracking → 실제 동작 설명
- `README_KR.md` (L263) — 동일 (한국어로 자연스럽게)
- `src/README.md` (L58 "CONFIDENCE NameError banner") — 동일
- `src/README_KR.md` (L58 "CONFIDENCE NameError 배너") — 동일

**손대지 않을 곳**:
- types/, useReports.ts, aggregate-*.mjs, batch-runner/, tests/, 다른 컴포넌트
- `src/data/tooltipTexts.ts` (UI PR이 이미 처리)
- `ErrorAnalysisView.tsx` (신규 컴포넌트 X)

## 현재 상태 (확인 완료)
TrendView.tsx 실제 코드:
```tsx
const successRateDomain: [number, number] = chartData.length > 0
  ? [Math.max(0, Math.floor(Math.min(...chartData.map((d) => d.successRate)) / 5) * 5 - 5), 100]
  : [0, 100]
// ...
<YAxis tick={tickStyle} domain={successRateDomain} />   // Success Rate (line ~121)
<YAxis tick={tickStyle} domain={[4, 7]} />              // QA Score (line ~141, HARDCODED)
```
- 데이터 필드명: `chartData`, `d.qaScore` (qa_score 아님)
- QA 점수 척도: 0~10

README 4줄 실제 내용:
- `README.md:263` → `| **Execution Errors** | Error distribution, recovery funnel, CONFIDENCE NameError tracking |`
- `README_KR.md:263` → `| **실행 에러** | 에러 분포, 복구 퍼널, CONFIDENCE NameError 추적 |`
- `src/README.md:58` → `| **Execution Errors** | Execution Errors | Error distribution, CONFIDENCE NameError banner, recovery funnel |`
- `src/README_KR.md:58` → `| **실행 에러** | Execution Errors | 에러 분포, CONFIDENCE NameError 배너, 복구 퍼널 |`

## Design — QA Score Y축
Success Rate 패턴과 일관되게 `qaScoreDomain` 상수 추가, `chartData.length > 0` 가드. QA는 0~10 척도:
```tsx
const qaScoreDomain: [number, number] = chartData.length > 0
  ? [
      Math.max(0, Math.floor(Math.min(...chartData.map((d) => d.qaScore)) * 2) / 2 - 0.5),
      Math.min(10, Math.ceil(Math.max(...chartData.map((d) => d.qaScore)) * 2) / 2 + 0.5),
    ]
  : [0, 7]
```
QA Score `<YAxis>`에 `domain={qaScoreDomain}` 적용.

## Design — CONFIDENCE README 정정
실제 동작: ErrorAnalysisView는 Exception Type 분포 차트 + AI 기반 Failure Insights 내러티브로 실패 패턴 가시화. 4줄 교체 예시:
- `README.md:263` → `| **Execution Errors** | Exception type distribution chart, recovery funnel, AI failure insights narrative |`
- `README_KR.md:263` → `| **실행 에러** | 예외 유형 분포 차트, 복구 퍼널, AI 기반 실패 인사이트 내러티브 |`
- `src/README.md:58` → `| **Execution Errors** | Execution Errors | Exception type distribution chart, recovery funnel, AI failure insights narrative |`
- `src/README_KR.md:58` → `| **실행 에러** | Execution Errors | 예외 유형 분포 차트, 복구 퍼널, AI 기반 실패 인사이트 내러티브 |`
(테이블 구조·열 수 유지, 기존 README 톤에 맞춰)

## Acceptance
- TrendView.tsx QA Score Y축 dynamic + 빈 데이터 가드 ([0,7] fallback)
- 4곳 README에서 "CONFIDENCE" 문자열 / "banner"·"배너" 광고 제거 (실제 동작 설명으로 대체, 테이블 깨지지 않음)
- `npm run build` 통과
- `grep -n 'domain={\[4' src/components/dashboard/TrendView.tsx` 0건
- `grep -ni 'CONFIDENCE' README.md README_KR.md src/README.md src/README_KR.md` 0건
- secrets 0
