# Phase B Combinations — 결과 분석

> 2026-05-24 17:35 UTC. GH Actions run #26363013282 — SUCCESS (223분).

## TL;DR

- **Phase B 5 variants 완료**, 추가 비용 $17.78 (누적 $37.22 / $80 cap)
- **새 우승자 없음** — Phase A의 `A4_model_mini`가 여전히 압도적
- **Tier 조합 모두 단일 mini보다 열등** — tiering 자체가 비효율 가설
- B5 (nano tier)는 critical_pass=0 — nano는 다시 한 번 채점 불가 확인

## Phase B 5 variants 결과

| variant | judge_model | tiering | avg | err | calls | crit | smoke $ | 풀런 $ |
|---|---|---|---|---|---|---|---|---|
| B1_baseline_ref | gpt-5.4-pro high | none | 78.7 | 5.9% | 84 | 1.0 | $7.29 | $534.59 |
| B2_std_med_b8 | gpt-5.4 medium | none, batch 8 | 72.4 | 0% | 18 | 1.0 | $0.88 | $64.54 |
| B3_tiered_pro_std_b8 | pro/std mix, batch 8 | 2-tier | 68.4 | 4.8% | 16 | 1.0 | $0.74 | $54.15 |
| B4_tiered_with_mini_b8 | pro/std/mini mix | 3-tier | 67.5 | 5.9% | 19 | 1.0 | $0.94 | $68.94 |
| **B5_tiered_with_nano_b8** | pro/std/nano mix | 3-tier (nano) | 66.0 | 5.9% | 15 | **0.0** | $0.71 | $52.36 |

## Insights

### 1. Tiering 자체가 score를 깎음
- B2 (단일 std batch 8): avg 72.4
- B3 (pro tier 추가): avg 68.4 (-4pp)
- B4 (+mini tier): avg 67.5 (-1pp 더)
- B5 (+nano tier): avg 66.0 (그리고 critical 망)

→ tier마다 다른 LLM이 다른 prompt 컨텍스트로 채점해서 verdict 일관성 깨짐.

### 2. B1_baseline_ref 재현 — baseline 시간 측정값 검증
- B1 avg=78.72, err=5.9% — Phase A의 A1_pro_high(71.4, 2.4%)와 차이
- 차이 원인: baseline은 `default_gpt5pro.yaml` 그대로 (extract=4000) vs A1_pro_high는 sweep template 기반(extract=1500). **extract=4000이 더 풍부한 evidence로 score 향상시킴**.
- 단 baseline err=5.9%는 alert 임계 살짝 초과 — baseline 자체가 prod에서 항상 5%대였음을 재확인.

### 3. **A4_model_mini가 모든 Phase B variant를 압도**
- A4_model_mini: avg 77.9, err 0%, $18.45 풀런
- B3 (가장 저렴 Phase B): avg 68.4 (-9.5pp), $54.15 풀런 (3× 더 비쌈)
- **단일 mini > 어떤 tier 조합**

### 4. Acceptance hard filter (critical=1, err≤5%, score±2pp)
- Phase B 통과: **0개** (모두 score delta 초과 또는 err 초과)
- Phase A 통과: **A2_std_extract_1500 (-0.83pp), A4_model_mini (+0.08pp)**

## 다음 단계 (Phase C — stability)

- dispatcher는 자동으로 "Phase B 중 critical=1.0인 top 2 by full_run_cost"를 선정
- 그게 곧 **B3 ($54)**, **B2 ($64)** 임 — 단 둘 다 score delta 큼 (-9, -5pp)
- → Phase C는 dispatcher 정의대로 진행하되, **최종 우승자는 사람이 결정 필요** (dispatcher Pareto + acceptance 결합).
- 실제 운영 후보는 여전히 **A4_model_mini**.

## 권고 — Phase C 후 결정

- **Recommended winner**: A4_model_mini (gpt-5.4-mini standalone, medium effort, no batching)
- 풀런 $18 / baseline $493 = **-96.3%** cost reduction with **+0.08pp score gain**.
- 단 stability를 위해 A4_model_mini를 3회 추가 stability run 권장 (Phase C 외부).
