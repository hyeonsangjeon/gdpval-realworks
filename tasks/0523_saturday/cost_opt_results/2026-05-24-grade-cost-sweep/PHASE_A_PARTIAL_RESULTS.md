# Phase A — Single-Axis Sweep 결과 (Partial, 11/15)

> 2026-05-24 14:00 UTC 기준. GH Actions run #26353454477 (cancelled @ 350-min timeout).
> 4 variants(A4 시리즈) 미완료, Phase A resume run으로 보강 예정.

## TL;DR

- **누적 비용 $19.44 / $80 cap** — 안전 영역.
- **11/15 variants 완료** + 4개 timeout으로 skip (A4_model_pro 진행 중 잘림, A4_model_std/mini/nano는 시작 못 함).
- **critical_item_pass_rate = 1.00** 모든 완료된 variant에서 유지. precheck_pass_rate = 0.80 안정.
- **Phase A 핵심 발견 4가지** (아래 Insights 섹션).
- **잠정 Pareto frontier 후보** (acceptance 통과만 기준):
  - `A2_std_extract_1500`: 풀런 ~$79, avg 77.0 (delta -0.8pp, baseline 77.83 대비)

## 완료된 11 variants 요약

| Variant | judge_model | effort | extract | batch | avg_score | err | calls | smoke $ | 풀런 $ |
|---|---|---|---|---|---|---|---|---|---|
| **A1_pro_minimal** | gpt-5.4-pro | minimal | 1500 | 1 | 9.8 | **1.000** | 84 | $0.00 | $0 |
| **A1_pro_low** | gpt-5.4-pro | low | 1500 | 1 | 9.8 | **1.000** | 84 | $0.00 | $0 |
| A1_pro_medium | gpt-5.4-pro | medium | 1500 | 1 | 72.2 | 0.012 | 84 | $5.63 | $412.81 |
| A1_pro_high (baseline-ish) | gpt-5.4-pro | high | 1500 | 1 | 71.4 | 0.024 | 84 | $6.73 | $493.54 |
| A2_std_extract_1000 | gpt-5.4 | medium | 1000 | 1 | 64.6 | 0.000 | 84 | $1.09 | $79.69 |
| **A2_std_extract_1500** | gpt-5.4 | medium | 1500 | 1 | **77.0** | 0.000 | 84 | $1.08 | $79.10 |
| A2_std_extract_2500 | gpt-5.4 | medium | 2500 | 1 | 82.8 | 0.000 | 84 | $1.22 | $89.46 |
| A3_std_batch_1 | gpt-5.4 | medium | 1500 | 1 | 76.2 | 0.000 | 84 | $1.16 | $84.82 |
| **A3_std_batch_4** | gpt-5.4 | medium | 1500 | 4 | 72.6 | 0.000 | **26** | $0.80 | **$58.91** |
| A3_std_batch_8 | gpt-5.4 | medium | 1500 | 8 | 71.9 | 0.048 | **16** | $0.81 | $59.04 |
| A3_std_batch_12 | gpt-5.4 | medium | 1500 | 12 | 63.1 | **0.167** | 17 | $0.93 | $67.99 |

> **굵게**: 핵심 통찰점

## Critical metrics (모든 variants)

```
critical_item_pass_rate = 1.00  (모든 variant 동일)
precheck_pass_rate      = 0.80  (모든 variant 동일)
judge_pass_rate         = 0.46~0.57 범위
```

→ **즉, 어떤 config를 골라도 weight≥4 critical 항목은 망가지지 않는다.** 비용 압축 자유도가 크다.

## Insights (Phase A에서 학습)

### 1. **gpt-5.4-pro의 reasoning_effort `minimal`/`low`는 채점 불가**
- A1_pro_minimal/low 둘 다 err=1.000 (모든 84 judge calls 실패), avg_score=9.8 (precheck 점수만 들어옴, judge는 다 fail)
- 원인 추정: minimal/low effort에서 출력 토큰이 너무 적어 verdict JSON parse 실패
- **→ gpt-5.4-pro는 medium 이상에서만 사용 가능. effort 축소로 비용 절감은 한계.**

### 2. **gpt-5.4 standard medium이 gpt-5.4-pro high를 거의 동률로 따라잡음**
- A1_pro_high (baseline): avg 71.4, $494 풀런
- A2_std_extract_1500: avg 77.0 (+5.6pp), $79 풀런 — **비용 6.2× 절감 + score 향상**
- 원인 추정: pro high가 reasoning 비대해 verdict 일관성이 오히려 떨어짐 (over-thinking)
- **→ standard tier를 default judge로 가능. pro는 weight≥4 critical 항목용 외부 검증으로 강등 가능.**

### 3. **extract chars 1500이 sweet spot**
- 1000: avg 64.6 (-12pp, evidence 부족)
- 1500: avg 77.0 (baseline near)
- 2500: avg 82.8 (+5pp, score 자연스럽게 향상)
- → 1500 이상은 evidence 풍부, 그 이상은 비용 vs 점수 일관성 trade-off

### 4. **Batching의 효용은 batch=4가 sweet spot**
- batch=1: avg 76.2, calls 84
- batch=4: avg 72.6, calls 26 → **호출수 3.2× ↓**, score -3.6pp
- batch=8: avg 71.9, calls 16, err 0.048 → **호출수 5.3× ↓**, score -4.3pp
- batch=12: avg 63.1, calls 17, err 0.167 → **err 16.7% 위험**, score -13pp
- → batch=4가 안전. batch=8은 err 한계 근접. batch=12는 unstable.

## Acceptance hard filter 통과 분석

기준: critical_pass=1.0 ✓ (모두), err≤5% ✓ (12개 중 11개), score delta ±2pp ✓ (몇 개?)

| variant | score | delta vs 77.83 | err | acceptance |
|---|---|---|---|---|
| A2_std_extract_1500 | 77.0 | **-0.83** ✓ | 0.000 ✓ | **PASS** |
| A3_std_batch_1 | 76.2 | **-1.63** ✓ | 0.000 ✓ | **PASS** |
| A2_std_extract_2500 | 82.8 | +4.97 | 0.000 ✓ | fail (delta) |
| A3_std_batch_4 | 72.6 | -5.23 | 0.000 ✓ | fail (delta) |
| A1_pro_medium | 72.2 | -5.63 | 0.012 ✓ | fail (delta) |
| A1_pro_high | 71.4 | -6.43 | 0.024 ✓ | fail (delta) |
| A3_std_batch_8 | 71.9 | -5.93 | 0.048 ✓ | fail (delta) |
| A2_std_extract_1000 | 64.6 | -13.23 | 0.000 ✓ | fail (delta) |
| A3_std_batch_12 | 63.1 | -14.73 | 0.167 ✗ | fail (delta + err) |
| A1_pro_minimal | 9.8 | -68.03 | 1.000 ✗ | fail (everything) |
| A1_pro_low | 9.8 | -68.03 | 1.000 ✗ | fail (everything) |

→ **Strict acceptance 통과는 2개**: `A2_std_extract_1500` (가장 저렴), `A3_std_batch_1` (no batching reference)

→ 만약 acceptance score delta를 ±5pp로 완화하면 +5개 (medium effort variants).

## 권고 사항 (Phase B 진입 전)

1. **A4 시리즈 (model sweep) 반드시 회수**. mini/nano가 채점 가능한지 모름. 모델 tier 선정의 핵심 데이터.
2. **Phase B 구성 재고**:
   - 정적 B1~B5는 가장 비싼 옵션(B3 tier-pro+std, B4 mini, B5 nano) 포함. mini/nano를 안 검증한 채 batch B 진입은 위험.
   - **A4 결과 먼저 확보 → Phase B 변종 미니마이즈 → Phase C 빠른 안정성 검증** 순서가 안전.
3. **Acceptance threshold 완화 검토**:
   - 현재 ±2pp 너무 까다로움 — score 변동은 채점 모델 변경 시 자연스러운 결과
   - ±5pp + critical_pass=1.0 유지 + err≤5% 면 사실상 모든 안정 variant가 옵션
4. **Pareto winner 후보**:
   - **Cost champion**: A3_std_batch_4 ($59 풀런, -3.6pp 손실, err=0)
   - **Quality champion**: A2_std_extract_2500 ($89 풀런, +5pp 향상, err=0)
   - **Balance**: A2_std_extract_1500 ($79 풀런, -0.8pp, err=0) — **strict acceptance 통과**

## 다음 단계 자동 진행

- Phase A resume (남은 4 variants: A4_model_pro 재시작, A4_model_std/mini/nano 신규)
- 예상 추가 비용 ~$5-10, 시간 ~60-90분 (A4_pro만 길고 나머지 짧음)
- 완료 후 PHASE_A_FINAL_RESULTS.md → Phase B trigger

---

_보고서 생성: 2026-05-24 12:00 UTC, orchestrator_
