# exp003 Head-to-Head — Single Mini vs Tiered (partial 40/220)

**Run A**: `default_gpt5pro.yaml` (single `gpt-5.4-mini` medium) — GH Actions run 26394620211
**Run B**: `tiered_critical_pro_mini.yaml` (pro for weight≥4, mini for rest) — GH Actions run 26394637568
**Experiment**: `exp003_GPT52Chat_baseline_runner_exec` (GPT-5.2-chat inference)
**Date**: 2026-05-25
**Status**: Both runs exited with code 1 after task #50; partial JSON saved at task #40 (partial_save_every_n_tasks=10). Direct head-to-head on same 40 tasks.

## TL;DR — 사용자 원안 (tiered)이 풀런에서 모든 metric에서 single-mini보다 열등

| Metric | A (single mini) | B (tiered) | Δ |
|---|---|---|---|
| avg_score_pct | 47.26 | 45.61 | −1.65pp |
| **critical_item_pass_rate** | **0.55** | **0.43** | **−0.12 (worse)** |
| judge_error_rate | 0.0073 | 0.0090 | +0.0017 |
| precheck_pass_rate | 0.77 | 0.77 | 0 |
| total_judge_latency | 6,002s (~100min) | **14,845s (~247min)** | **+2.5× slower** |
| output tokens | 871,596 | 1,021,553 | +17% |
| estimated cost (40 tasks) | ~$1.7 | **~$25** | **~15× more expensive** |

→ **사용자 원안 reject. Single-mini default 유지.**

## Why tiered is worse — 가설

`tier_pro` (gpt-5.4-pro, reasoning_effort=high) judge가 weight ≥ 4 항목에 대해:

1. **더 깐깐한 verdict** 발급: high effort에서 reasoning이 깊어져 borderline 항목을 fail 처리하는 경향
2. 결과적으로 **critical_pass 자체가 낮아짐** (사용자 의도와 정반대 — pro는 critical을 더 통과시킬 것으로 기대했지만 실제로는 더 떨어뜨림)
3. 또한 pro high effort는 호출당 30~60초 vs mini의 5~10초 → wall-clock 2.5× 증가
4. 토큰 비용도 reasoning 토큰 폭증으로 increase

이 패턴은 Sweep Phase A에서도 관찰됨:
- A1_pro_high: avg 71.4 (vs A2_std_extract_1500: 77.0)
- pro high가 standard medium보다 점수가 낮음 → "over-thinking" 가설 강화

## Acceptance gate (TASK_TIERED_VALIDATION.md 기준)

| 기준 | 결과 |
|---|---|
| tiered.critical_pass ≥ mini.critical_pass | **FAIL** (0.43 < 0.55) |
| `\|`avg_score Δ`\|` ≤ 5pp | PASS (1.65pp) |
| tiered err_rate ≤ 5% | PASS (0.9%) |
| tiered cost ≤ 2× mini | **FAIL** (~15× 더 비쌈) |

→ **2개 기준 fail → tiered를 default로 채택하지 않음.** Single-mini default 유지.

## 비정상 score 발견

`ff85ee58-bc9` task: `total_max = -57` (음수 max_score). 이건 rubric 자체에 penalty items가 있어서 max 합산이 음수가 되는 케이스. mini judge나 pro judge의 문제가 아니라 step8_grade.py의 score normalization이 음수 max를 처리 안 함. 양 run 동일하게 발견 → grading config 무관.

## step8_grade.py task #50 unhandled exception (별도 버그)

**두 run이 정확히 같은 task 50 (`d025a41c`) 처리 직후 exit 1**, traceback 없음. 가능성:
- Memory accumulation (GH Actions runner 메모리 한도)
- Schema validation 실패 후 sys.exit(1)
- 외부 dependency (HF download 부분 손상?)

이건 cost optimization과 별개 issue. 별도 `TASK_STEP8_TASK50_FAIL.md`로 트래킹 권장.

## Cost finding — exp003 풀런 외삽

40 task 데이터 × 5.5 (220/40):
- Run A 풀런 추정: ~$10 cost / ~9h wall-clock (mini 단독)
- Run B 풀런 추정: ~$140 cost / ~22h wall-clock — **timeout 위험** (GH Actions 480분 cap)

→ Tiered config는 비용/시간 모두 single-mini의 ~15×. 채택 불가.

## 결정

1. **default_gpt5pro.yaml은 single-mini로 유지** (현재 main 상태 그대로)
2. `tiered_critical_pro_mini.yaml`은 main에 남기되 **default 후보가 아님**으로 문서화. 향후 다른 critical 정의(예: weight≥5만)로 재실험 시 base로 사용.
3. step8_grade.py task #50 fail은 별도 task로 트래킹
4. exp003 partial grade JSONs은 main에 commit하지 않음 (40 task only, 비교 분석 끝나면 보존 불필요). artifact에는 30일 유지.

## Caveats

- 40 task only — 220 task 완전 검증 아님. 단 두 run 동일 task에서 fail이라 head-to-head 비교는 valid.
- exp003 inference quality 자체가 critical_pass 0.55 수준 (GPT-5.2-chat baseline). mini 채점 정확도 문제가 아니라 inference quality 반영일 가능성.
- pro tier의 score depression 결론은 exp003 single 측정. 다른 inference 모델(예: 더 강한 모델)의 deliverable에서도 같은 패턴인지는 미검증.

---

_보고서 생성: 2026-05-25 16:30 UTC. orchestrator._
