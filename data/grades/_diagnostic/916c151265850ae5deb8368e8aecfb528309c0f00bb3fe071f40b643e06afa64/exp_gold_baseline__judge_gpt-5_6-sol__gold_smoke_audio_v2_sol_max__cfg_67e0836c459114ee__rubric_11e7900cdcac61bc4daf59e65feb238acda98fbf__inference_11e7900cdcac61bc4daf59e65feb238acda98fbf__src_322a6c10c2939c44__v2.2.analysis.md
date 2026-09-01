# Grade Run Analysis — exp_gold_baseline

- file: `data/grades/_diagnostic/916c151265850ae5deb8368e8aecfb528309c0f00bb3fe071f40b643e06afa64/exp_gold_baseline__judge_gpt-5_6-sol__gold_smoke_audio_v2_sol_max__cfg_67e0836c459114ee__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_322a6c10c2939c44__v2.2.json`
- config: `gold_smoke_audio_v2_sol_max` (model=gpt-5.6-sol, effort=max)
- tasks: 2/2 (errors=0)

## Quality
- avg_score_pct: **32.56**
- critical_item_pass_rate: **0.5**
- judge_pass_rate: 0.2466
- judge_error_rate: 0.0685
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-08-31T10:29:55+00:00 → 2026-08-31T10:45:18+00:00
- **wall-clock**: 15.4 min
- sum judge latency: 31.9 min (concurrency factor ≈ 2.07x)
- per-task: avg=956.0s, p50=956.0s, p95=995.2s

## Volume
- total API calls: 237 (main=218, perception=19)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=563,767  out=44,324
- main tokens: in=555,319 out=42,913; perception tokens: in=8,448 out=1,411
- render: calls=0, latency=0.0 min; usage_complete=False
- per-task avg (in,out): (281884, 22162)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 997.5 | 102 / 256099,19322,217286 / 953.26s | 0 / 0,0,0 / 0.0s | 7 / 2945,523,0 / 41.98s | 0 / 0,0,0 / 0.0s | InternalServerError:1, required_visual_render_target_unavailable:1 |
| `75401f7c-396d-406d-b08e-938874ad1045` | 923.73 | 116 / 299220,23591,256855 / 862.47s | 0 / 0,0,0 / 0.0s | 12 / 5503,888,0 / 54.32s | 0 / 0,0,0 / 0.0s | required_visual_render_target_unavailable:3 |

- judge_error_types: InternalServerError:1, required_visual_render_target_unavailable:4
- projected_220_wall_hours: 58.7 (at_or_above_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: unpriced (gpt-5.6-sol,gpt-audio-1.5)
- effective (cached-discounted): unpriced (gpt-5.6-sol,gpt-audio-1.5)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 995.2 | 109 | (259044, 19845) | 18.97 | True |
| `75401f7c-396d-406d-b08e-938874ad1045` | 916.8 | 128 | (304723, 24479) | 46.16 | True |
