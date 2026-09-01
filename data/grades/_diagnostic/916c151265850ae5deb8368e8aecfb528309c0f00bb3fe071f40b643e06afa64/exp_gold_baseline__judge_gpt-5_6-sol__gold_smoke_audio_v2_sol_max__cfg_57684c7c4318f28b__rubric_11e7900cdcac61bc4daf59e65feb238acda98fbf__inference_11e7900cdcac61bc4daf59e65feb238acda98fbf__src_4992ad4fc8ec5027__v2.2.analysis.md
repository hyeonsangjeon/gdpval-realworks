# Grade Run Analysis — exp_gold_baseline

- file: `data/grades/_diagnostic/916c151265850ae5deb8368e8aecfb528309c0f00bb3fe071f40b643e06afa64/exp_gold_baseline__judge_gpt-5_6-sol__gold_smoke_audio_v2_sol_max__cfg_57684c7c4318f28b__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_4992ad4fc8ec5027__v2.2.json`
- config: `gold_smoke_audio_v2_sol_max` (model=gpt-5.6-sol, effort=max)
- tasks: 2/2 (errors=0)

## Quality
- avg_score_pct: **26.37**
- critical_item_pass_rate: **0.5**
- judge_pass_rate: 0.1918
- judge_error_rate: 0.0548
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-08-31T11:49:26+00:00 → 2026-08-31T12:00:17+00:00
- **wall-clock**: 10.8 min
- sum judge latency: 19.4 min (concurrency factor ≈ 1.8x)
- per-task: avg=582.1s, p50=582.1s, p95=643.6s

## Volume
- total API calls: 233 (main=216, perception=17)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=560,885  out=45,505
- main tokens: in=553,308 out=44,248; perception tokens: in=7,577 out=1,257
- render: calls=0, latency=0.0 min; usage_complete=True
- per-task avg (in,out): (280442, 22752)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 522.94 | 100 / 252247,18855,215852 / 506.44s | 0 / 0,0,0 / 0.0s | 7 / 3007,500,0 / 14.26s | 0 / 0,0,0 / 0.0s | required_visual_render_target_unavailable:1 |
| `75401f7c-396d-406d-b08e-938874ad1045` | 650.96 | 116 / 301061,25393,261952 / 625.43s | 0 / 0,0,0 / 0.0s | 10 / 4570,757,0 / 18.14s | 0 / 0,0,0 / 0.0s | required_visual_render_target_unavailable:3 |

- judge_error_types: required_visual_render_target_unavailable:4
- projected_220_wall_hours: 35.87 (below_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: unpriced (gpt-5.6-sol,gpt-audio-1.5)
- effective (cached-discounted): unpriced (gpt-5.6-sol,gpt-audio-1.5)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `75401f7c-396d-406d-b08e-938874ad1045` | 643.6 | 126 | (305631, 26150) | 36.07 | True |
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 520.7 | 107 | (255254, 19355) | 16.67 | True |
