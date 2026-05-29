# Grade Run Analysis — exp003_GPT52Chat_baseline_runner_exec

- file: `data/grades/exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-mini__11e7900__v1.json`
- config: `default_gpt5pro` (model=gpt-5.4-mini, effort=medium)
- tasks: 219/220 (errors=1)

## Quality
- avg_score_pct: **51.47**
- critical_item_pass_rate: **0.5177**
- judge_pass_rate: 0.383
- judge_error_rate: 0.0036
- precheck_pass_rate: 0.8384

## Wall-clock & latency
- first→last graded_at: 2026-05-28T21:33:08+00:00 → 2026-05-29T07:05:41+00:00
- **wall-clock**: 572.5 min
- sum judge latency: 524.0 min (concurrency factor ≈ 0.92x)
- per-task: avg=142.9s, p50=138.4s, p95=277.1s

## Volume
- judge calls: 9958  |  precheck decisions: 548  (judge share 94.8%)
- tokens: in=16,498,073  out=4,544,653
- per-task avg (in,out): (74991, 20658)

## Cost estimate
- $8.67  (model=gpt-5.4-mini; in=$4.12, out=$4.54)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `40a8c4b1-b169-4f92-a38b-7f79685037ec` | 421.0 | 72 | (221398, 67609) | 23.57 | False |
| `90edba97-74f0-425a-8ff6-8b93182eb7cb` | 315.7 | 52 | (204280, 50831) | 49.19 | False |
| `a73fbc98-90d4-4134-a54f-2b1d0c838791` | 310.6 | 59 | (142271, 53409) | 36.21 | False |
| `d7cfae6f-4a82-4289-955e-c799dfe1e0f4` | 309.7 | 53 | (129607, 48619) | 65.16 | False |
| `6974adea-8326-43fa-8187-2724b15d9546` | 308.7 | 68 | (235283, 42183) | 63.15 | False |
