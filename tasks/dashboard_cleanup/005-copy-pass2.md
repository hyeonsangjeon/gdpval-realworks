# 005 — Copy pass 2 (self-assessed vs LLM-judge 혼동 잡기)

## 목적

PR #46에서 "external grading pipeline" 카피는 정리했지만, "self-assessed
QA score" 와 "LLM-judge grade" 가 별개라는 점이 여전히 모호. 사용자가
KPI 카드 / 카드 sub-text 보고 두 메트릭을 혼동.

## 원칙

매 카피마다 다음을 명시:
1. self-assessed QA 는 inference 단계 **자체평가** — judge 와 별개.
2. LLM-judge grade 는 별도 파이프라인 (grade-run.yml) 산출물.
3. 두 점수는 **서로 검증하지 않음** — 다른 차원의 신호.

## 변경 파일

| 파일 | 변경 |
|---|---|
| `src/data/tooltipTexts.ts` | KPI / leaderboard / grading 토큰 정리 |
| `src/components/AnalysisCard.tsx` | QA score sub-label clarify |
| `src/components/dashboard/LeaderboardView.tsx` | column header tooltip clarify |
| `src/components/dashboard/TrendView.tsx` | y-axis label clarify (있다면) |
| `src/pages/Dashboard.tsx` | top KPI labels (있다면) |

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

기존:
```
"Percentage of tasks that passed self-assessed QA. Higher is better.
 Color: ≥96% green, ≥90% amber, <90% red."
```

변경:
```
"Percentage of tasks that passed the LLM's self-QA check. Self-assessed
 (model judging itself) — separate from the LLM-judge grade. Colors:
 ≥96% green, ≥90% amber, <90% red."
```

### tooltipTexts.leaderboard.qaScore

기존:
```
"Average quality score (0–10) across completed tasks. Self-assessed by
 the LLM after each task."
```

변경:
```
"Average self-QA score (0–10), model rates its own output. Independent
 from the LLM-judge grade (see Grading Analysis tab)."
```

### tooltipTexts.badge.selfAssessed

기존:
```
"Score is based on the LLM's own QA self-assessment. Amber badge =
 LLM-judge grade not yet available (run grade-run.yml to populate)."
```

변경 (002 와 정합 — `grade_status` 사용):
```
"This experiment has no LLM-judge grade yet. Numbers shown come from
 the model's own self-QA check during inference (independent signal).
 Run grade-run.yml to generate rubric-based grades."
```

### tooltipTexts.aboutContent.sections[2].bullets

기존:
```
[
  "Success Rate — Did the LLM produce a valid deliverable?",
  "QA Score (0-10) — Self-assessed quality of the output",
  "Grading — LLM-judge against open-sourced GDPval rubrics (when available)",
]
```

변경 (순서 + 명시):
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

## 컴포넌트별 추가 카피

### LeaderboardView column 라벨 (있다면)
- "QA Score" → "Self-QA" 또는 "Self-QA (0-10)" 로 단축 라벨 사용
  (overflow 우려 시 InfoTooltip 으로 풀어 설명)

### TrendView y-axis (있다면)
- "Success rate" 그래프 옆에 작은 sub-text: "self-QA based"

## 회귀 테스트

- `grep -rE "Self-QA|self-QA|LLM-judge|self-assessed" src/data/tooltipTexts.ts`
  → 모든 self-vs-judge 분리 카피가 살아있는지
- 시각 회귀: dashboard 메인 페이지에서 임의 KPI 카드 호버 시 새 카피 노출

## 의존성

- 002 (grade_status) — `selfAssessed` 배지 카피가 status 기반
- 001 (model display) — 직접 의존 X

## 비고

- 카피 변경만으로 5KB 미만 bundle 영향. 빌드 캐시 무관.
- i18n 미사용 (이 repo는 영문 일관). 한글 버전 별도 작업 시 005-ko.md
  별도 발행.
