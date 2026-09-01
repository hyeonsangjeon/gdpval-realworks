# Grade Run Analysis — exp_gold_baseline

- file: `data/grades/_diagnostic/916c151265850ae5deb8368e8aecfb528309c0f00bb3fe071f40b643e06afa64/exp_gold_baseline__judge_gpt-5_6-sol__gold_smoke_audio_v2_sol_max__cfg_ddacb72418fc5400__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_f9ecc9e27ceb57b4__v2.2.json`
- config: `gold_smoke_audio_v2_sol_max` (model=gpt-5.6-sol, effort=max)
- tasks: 2/2 (errors=0)

## Quality
- avg_score_pct: **26.41**
- critical_item_pass_rate: **0.5**
- judge_pass_rate: 0.1233
- judge_error_rate: 0.3151
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-08-31T06:22:09+00:00 → 2026-08-31T06:33:22+00:00
- **wall-clock**: 11.2 min
- sum judge latency: 20.8 min (concurrency factor ≈ 1.86x)
- per-task: avg=622.5s, p50=622.5s, p95=665.6s

## Volume
- total API calls: 229 (main=223, perception=6)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=571,929  out=47,714
- main tokens: in=571,929 out=47,714; perception tokens: in=0 out=0
- render: calls=0, latency=0.0 min; usage_complete=False
- per-task avg (in,out): (285964, 23857)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 581.9 | 101 / 255165,21092,215861 / 578.62s | 0 / 0,0,0 / 0.0s | 3 / 0,0,0 / 0.79s | 0 / 0,0,0 / 0.0s | audio_perception_failed:7, required_visual_render_target_unavailable:1 |
| `75401f7c-396d-406d-b08e-938874ad1045` | 672.65 | 122 / 316764,26622,277326 / 665.06s | 0 / 0,0,0 / 0.0s | 3 / 0,0,0 / 0.55s | 0 / 0,0,0 / 0.0s | audio_perception_failed:12, required_visual_render_target_unavailable:3 |

- judge_error_types: audio_perception_failed:19, required_visual_render_target_unavailable:4
- projected_220_wall_hours: 38.33 (below_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: unpriced (gpt-5.6-sol)
- effective (cached-discounted): unpriced (gpt-5.6-sol)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `75401f7c-396d-406d-b08e-938874ad1045` | 665.6 | 125 | (316764, 26622) | 36.15 | True |
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 579.4 | 104 | (255165, 21092) | 16.67 | True |
