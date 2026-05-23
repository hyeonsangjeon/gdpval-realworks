# 005 — Copy pass 2 (self-assessed vs LLM-judge 혼동 잡기)

> **Amendments (post extreme-reasoner review)**:
> - 구현자가 enumerate된 파일에 의존하지 말고, **mandatory grep audit**
>   을 거쳐 모든 매치를 reconcile. 명시 누락 가능성 가드.
> - 추가 확인 대상: `GradingAnalysisView` empty state, `GradesSummary`
>   dummy banner, `GradeDetail` TERM_DEFINITIONS, `ExperimentDetail`
>   narrative body.

## 목적

PR #46에서 "external grading pipeline" 카피는 정리했지만, "self-assessed
QA score" 와 "LLM-judge grade" 가 별개라는 점이 여전히 모호. 사용자가
KPI 카드 / 카드 sub-text 보고 두 메트릭을 혼동.

## 원칙

매 카피마다 다음을 명시:
1. self-assessed QA 는 inference 단계 **자체평가** — judge 와 별개.
2. LLM-judge grade 는 별도 파이프라인 (grade-run.yml) 산출물.
3. 두 점수는 **서로 검증하지 않음** — 다른 차원의 신호.

## Mandatory grep audit (구현 1단계, gate)

구현자는 다음 grep을 **반드시** 실행하고 모든 매치를 표로 기록하여
PR description에 첨부:

```bash
rg -i "self-?QA|self-?assess|LLM-?judge|external grad|grading pipeline|pre-?grad|Awaiting" \
   src/ scripts/aggregate-grades.mjs
```

각 매치 행은 다음 세 가지 중 하나로 분류:
- **OK** — 이미 새 원칙 준수
- **EDIT** — 카피 수정 필요 (이 spec에 포함)
- **DELETE** — 더 이상 의미 없음 (이 spec에 포함)

PR review 시 "OK" 외엔 모두 처리됐는지 검증.

## 변경 파일 (예상)

| 파일 | 변경 |
|---|---|
| `src/data/tooltipTexts.ts` | KPI / leaderboard / grading 토큰 정리 + 새 `grading.judgeVsInference` |
| `src/components/AnalysisCard.tsx` | QA score sub-label clarify |
| `src/components/dashboard/LeaderboardView.tsx` | column header tooltip clarify |
| `src/components/dashboard/GradingAnalysisView.tsx` | empty state + 본문 카피 |
| `src/components/dashboard/TrendView.tsx` | y-axis label clarify (있다면) |
| `src/pages/Dashboard.tsx` | top KPI labels (있다면) |
| `src/pages/GradeDetail.tsx` | `TERM_DEFINITIONS` 재검토 |
| `src/pages/ExperimentDetail.tsx` | narrative body의 LLM-judge 표현 |

## 카피 변경 명세

### tooltipTexts.kpi.bestSuccessRate

기존:
```
"Highest task-completion rate among all experiments. A task is "successful"
 when the LLM's self-assessed QA check passes (based on self-assessed QA —
 separate from LLM-judge grade)."
```

변경:
```
"Highest task-completion rate based on the LLM's self-QA check during
 inference. This is the model judging its own deliverable — NOT the same
 as the LLM-judge grade (rubric-based, run via grade-run.yml). Both
 signals are independent."
```

### tooltipTexts.kpi.bestQaScore

기존:
```
"Highest average Self-QA score (0–10) across experiments. … not an
 LLM-judge grade."
```

변경:
```
"Highest average Self-QA score (0–10): the LLM rates its own output
 right after generation. Useful for runtime quality signal but does NOT
 imply rubric correctness — for that see the LLM-judge grade (Grading
 Analysis tab)."
```

### tooltipTexts.leaderboard.successRate

변경:
```
"Percentage of tasks that passed the LLM's self-QA check. Self-assessed
 (model judging itself) — separate from the LLM-judge grade. Colors:
 ≥96% green, ≥90% amber, <90% red."
```

### tooltipTexts.leaderboard.qaScore

변경:
```
"Average self-QA score (0–10), model rates its own output. Independent
 from the LLM-judge grade (see Grading Analysis tab)."
```

### tooltipTexts.badge.selfAssessed

변경 (002 와 정합 — `grade_status` 사용):
```
"This experiment has no LLM-judge grade yet. Numbers shown come from
 the model's own self-QA check during inference (independent signal).
 Run grade-run.yml to generate rubric-based grades."
```

### tooltipTexts.grading (신규 키)

```ts
grading: {
  // …existing keys…
  judgeVsInference:
    "LLM-judge model evaluates outputs against the rubric. Distinct from the inference model that produced them.",
}
```

### tooltipTexts.aboutContent.sections[2].bullets

변경:
```
[
  "Success Rate — Did inference complete with a deliverable that passed self-QA?",
  "Self-QA Score (0-10) — Model's own rating of its output (runtime signal)",
  "LLM-Judge Grade — Independent rubric-based scoring run via grade-run.yml (Grading Analysis tab)",
  "Note: Self-QA and LLM-judge grade are independent signals — high self-QA does not guarantee high rubric grade.",
]
```

### sectionHintTexts

`sectionHintTexts.leaderboard`:
```
Each row is one experiment — same {TASK_TOTAL} real-world tasks,
different prompt strategies. Numbers here reflect inference-time
self-QA. For rubric-based grades, switch to the Grading Analysis tab.
```

## 추가 확인 (extreme-reasoner D1)

### GradingAnalysisView empty state (line 117-119)

기존:
```
"Grading results will appear here after running the LLM-judge via grade-run.yml.
 This is separate from the self-assessed QA scores shown in other tabs."
```

→ OK (이미 명시). 톤 일관성만 재확인.

### GradesSummary dummy banner (line 116-117)

기존: `"⏳ Awaiting LLM-Judge Grade — run grade-run.yml to populate"`

→ 002 D3 에서 DEMO badge 로 교체되며 자동 정리.

### GradeDetail TERM_DEFINITIONS (line 43-52)

```ts
const TERM_DEFINITIONS = {
  graded: 'Tasks that received a score — excludes any that errored out.',
  perfect: 'Score = 100% — all rubric criteria were fully satisfied.',
  partial: 'Score between 0–100% — some rubric criteria were met.',
  zero: 'Score = 0% — no rubric criteria were satisfied.',
  // ...
}
```

→ OK (rubric language 사용 중, self-QA와 혼동 없음). 변경 불필요.

### ExperimentDetail narrative body

PR 구현 시 `rg "LLM-judge|self-QA|self-assessed" src/pages/ExperimentDetail.tsx`
실행하여 누락 매치 처리.

## 컴포넌트별 추가 카피

### LeaderboardView column 라벨
- "QA Score" → "Self-QA" 또는 "Self-QA (0-10)" 로 단축 라벨 사용
  (overflow 우려 시 InfoTooltip 으로 풀어 설명)

### TrendView y-axis (있다면)
- "Success rate" 그래프 옆에 작은 sub-text: "self-QA based"

## 회귀 테스트

- `rg -i "self-?QA|self-?assess|LLM-?judge|external grad|grading pipeline|pre-?grad" src/`
  → 모든 매치가 self-vs-judge 분리 카피로 정리되어 있는지
- 시각 회귀: dashboard 메인 페이지에서 임의 KPI 카드 호버 시 새 카피 노출

## 의존성

- 002 (grade_status) — `selfAssessed` 배지 카피가 status 기반
- 001 (model display) — `grading.judgeVsInference` tooltip 사용

## 비고

- 카피 변경만으로 5KB 미만 bundle 영향. 빌드 캐시 무관.
- i18n 미사용. 한글 버전 별도 작업 시 005-ko.md 별도 발행.

