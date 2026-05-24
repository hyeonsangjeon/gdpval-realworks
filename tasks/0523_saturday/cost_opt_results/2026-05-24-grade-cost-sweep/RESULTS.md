# Grading Cost Sweep — Results

- **Run**: 2026-05-24T05:59:40Z → 2026-05-24T17:00:31Z
- **Plan**: cost_opt_sweep_v1
- **Benchmark**: exp998_smoke_baseline_sample, 3 tasks, rubric `11e7900`
- **Cumulative cost**: $37.22 / cap $80

## TL;DR

**Winner**: `A4_model_mini`

- 풀런 예상 비용: $18.45
- avg_score_pct: 77.91 (baseline 77.83, Δ +0.08pp)
- critical_item_pass_rate: 1.00
- judge_error_rate: 0.0%
- wall-clock (smoke): 299s
- Rationale: Pareto winner among 3 eligible variants (frontier size 1); minimized full_run_cost_usd.

## Phase A: Single-axis sweep

| variant | avg_score | crit_pass | err | calls | latency | smoke $ | full $ |
|---|---|---|---|---|---|---|---|
| A1_pro_minimal | 9.76 | 0.00 | 100.0% | 84 | 0s | $0.00 | $0.00 |
| A1_pro_low | 9.76 | 0.00 | 100.0% | 84 | 0s | $0.00 | $0.00 |
| A1_pro_medium | 72.23 | 1.00 | 1.2% | 84 | 4650s | $5.63 | $412.81 |
| A1_pro_high | 71.43 | 1.00 | 2.4% | 84 | 7902s | $6.73 | $493.54 |
| A2_std_extract_1000 | 64.60 | 1.00 | 0.0% | 84 | 479s | $1.09 | $79.69 |
| A2_std_extract_1500 | 77.03 | 1.00 | 0.0% | 84 | 473s | $1.08 | $79.10 |
| A2_std_extract_2500 | 82.77 | 1.00 | 0.0% | 84 | 490s | $1.22 | $89.46 |
| A3_std_batch_1 | 76.17 | 1.00 | 0.0% | 84 | 525s | $1.16 | $84.82 |
| A3_std_batch_4 | 72.64 | 1.00 | 0.0% | 26 | 455s | $0.80 | $58.91 |
| A3_std_batch_8 | 71.89 | 1.00 | 4.8% | 16 | 497s | $0.81 | $59.04 |
| A3_std_batch_12 | 63.12 | 1.00 | 16.7% | 17 | 570s | $0.93 | $67.99 |
| A4_model_pro | 72.92 | 1.00 | 2.4% | 84 | 4504s | $5.88 | $430.96 |
| A4_model_std | 74.42 | 1.00 | 0.0% | 84 | 481s | $1.10 | $80.46 |
| A4_model_mini | 77.91 | 1.00 | 0.0% | 84 | 299s | $0.25 | $18.45 |
| A4_model_nano | 9.76 | 0.00 | 100.0% | 84 | 0s | $0.00 | $0.00 |

## Phase B: Combinations

| variant | avg_score | crit_pass | err | calls | latency | smoke $ | full $ |
|---|---|---|---|---|---|---|---|
| B1_baseline_ref | 78.72 | 1.00 | 5.9% | 84 | 8411s | $7.29 | $534.59 |
| B2_std_med_b8 | 72.41 | 1.00 | 0.0% | 18 | 565s | $0.88 | $64.54 |
| B3_tiered_pro_std_b8 | 68.42 | 1.00 | 4.8% | 16 | 576s | $0.74 | $54.15 |
| B4_tiered_with_mini_b8 | 67.55 | 1.00 | 5.9% | 19 | 755s | $0.94 | $68.94 |
| B5_tiered_with_nano_b8 | 66.00 | 0.00 | 5.9% | 15 | 557s | $0.71 | $52.36 |

## Diversity Validator

| variant | avg_score | crit_pass | err | calls | latency | smoke $ | full $ |
|---|---|---|---|---|---|---|---|
| DV_gpt4o_medium_b8 | 9.76 | 0.00 | 100.0% | 12 | 0s | $0.00 | $0.00 |

## Winner Config

See `winner_config.yaml`. Promote to `batch-runner/grading_configs/recommended_<date>.yaml` after a manual full-run validation against baseline.

## Caveats

- Smoke costs are token-based estimates (variance vs. tenant billing ≤ ~20%).
- Full-run cost is linear extrapolation × 73.3.
- gpt-5.5 is out-of-scope (quota pending).
