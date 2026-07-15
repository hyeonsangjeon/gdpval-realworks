# TASK_TIERED_VALIDATION — Full-run 비교 (single-mini vs tiered) on exp003

> 작성: 2026-05-25 (Monday)
> 결정 게이트: 명세 원안(tiered)이 단일 mini보다 critical/score에서 유의미하게 우월하면 default를 tiered로 교체. 아니면 single-mini 유지.

## TL;DR

Sweep winner(`A4_model_mini` = 단일 mini)가 **smoke 3-task** 기준으로만 검증돼 있다. 명세 원안인 **tiered routing(pro for critical, mini for rest)**이 실제로는 더 안전할 수 있는데, smoke 표본이 작아 결정에 신뢰가 부족하다.

→ **`exp003_GPT52Chat_baseline_runner_exec` (220 tasks, HF deliverables 629개)**으로 풀런 2회 head-to-head:

1. **Run A** — `default_gpt5pro.yaml` (현재 = single mini)
2. **Run B** — `tiered_critical_pro_mini.yaml` (신규: critical은 pro, 나머지는 mini)

결과 비교 후 **A가 더 나은 방향(tiered)** 이면 default 교체 PR. 아니면 single-mini 유지.

## Why exp003

- HF dataset `HyeonSang/exp003_GPT52Chat_baseline_runner_exec` 에 **deliverables 629개** 존재 (대조: exp001 = 0, 사용 불가)
- GPT-5.2-chat baseline 실험이라 다양한 sector/occupation 커버
- 비용 추정: 풀런 1회 ~$18 (mini) ~ $25-30 (tiered) = 합산 **~$45**, configured run-level cost guard 내에서 실행

## Acceptance criteria (tiered 채택 조건)

다음 **모두** 충족 시 tiered가 "더 나은 방향" → default 교체:
- critical_item_pass_rate: tiered ≥ mini (단조 비우월이라도 동등 허용)
- avg_score_pct: |tiered − mini| ≤ 5pp (큰 변화 없어야 함; 작은 변화는 OK)
- judge_error_rate: tiered ≤ 5%
- 비용 증가: tiered cost ≤ 2× mini cost (수용 가능한 증가폭)

**둘 중 하나라도 미충족** → single-mini 유지.

## Tiered config 사양

`batch-runner/grading_configs/tiered_critical_pro_mini.yaml`:

- `judge` (top-level, fallback): gpt-5.4-mini medium (= 현재 default와 동일, 캐시 키 호환)
- `judge_routing`:
  - `tier_pro`: gpt-5.4-pro, reasoning_effort: high, route_when: weight_gte: 4
  - `tier_standard`: gpt-5.4-mini, reasoning_effort: medium (대다수 항목)
  - (tier_mini는 생략 — minimal-effort fuzzy precheck는 별도 검증 필요)
- `grader`:
  - `batch_size`: 1 (sweep Phase A에서 batching이 variance 큼 확인)
  - `deliverable_extract_max_chars`: 1500 (sweep A2 sweet spot)

## Critical 기준 (weight ≥ 4)

명세 원안의 "critical items"는 rubric weight ≥ 4. rubric loader에서 확인:
- 정확한 weight 분포는 sweep 결과로 추정 약 10~15% items
- 그게 정확하지 않으면 tiered effective 비중이 달라지므로 보고서에 명시 필요

## 실행 순서 (자율 dispatch)

```
Step 1: task spec commit (이 문서)Step 2: Tiered config 작성 + commit + 검증 + push (main 직접 OK — config 추가만)Step 3: Run A trigger — exp003 with default_gpt5pro.yaml (mini)
Step 4: Run A 모니터링 (예상 ~5h)
Step 5: Run B trigger — exp003 with tiered_critical_pro_mini.yamlStep 6: Run B 모니터링 (예상 ~6h, pro 일부 포함)
Step 7: 비교 분석 → COMPARISON_REPORT.md 작성
Step 8: Acceptance 통과 시:
    8a. 새 PR: default_gpt5pro.yaml → tiered 사양으로 교체
    8b. CHANGELOG에 결과 + 결정 기록
    8c. PR 머지
    8d. exp003 dashboard 확인
Step 9: Acceptance 미통과 시:
    9a. 결과만 보고 + tiered config는 named config로 두기
    9b. CHANGELOG에 "tiered config 도입 보류" 기록
```

## Stop conditions

- Run A 또는 B에서 critical_pass < 0.95 → 즉시 중단 + 보고
- GH Actions timeout (480분) 초과 시 partial 결과로 분석
- 누적 비용 $60 초과 시 abort (run-level cost guard)
- HF download가 또 0 파일이면 즉시 보고 (다른 후보 실험 선택)

## Files

- `tasks/0525_monday/TASK_TIERED_VALIDATION.md` (이 파일)
- `batch-runner/grading_configs/tiered_critical_pro_mini.yaml` (Step 2 생성)
- `tasks/0525_monday/COMPARISON_REPORT.md` (Step 7 생성)
- `data/grades/exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-mini__11e7900__v1.json` (Run A 산출물)
- `data/grades/exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-pro__11e7900__v1.json` (Run B 산출물, 우승 모델로 표기)

## Caveats

- Tiered config의 `judge_routing.tier_pro.route_when.weight_gte=4`가 effective 항목 비율을 결정. rubric의 실제 weight 분포가 측정 안 됐다면 결과 해석 시 표본 분포도 함께 보고.
- 비용 추정은 `scripts/grading_cost_sweep.py` PRICING table 기반 working estimate. 실제 청구는 ±20% 가능.
- gpt-4o 같은 diversity validator는 본 task에서 제외 (Responses API 호환성 문제로 sweep에서 실패함).
