# Grade Run Analysis — exp_gold_baseline

- file: `data/grades/_diagnostic/b16d9b188a763fa9382d9b18df796b2f08cf284b47619195a2feba963149063c/exp_gold_baseline__judge_gpt-5_6-sol__gold_audio_repeat_v2_sol_max__cfg_ed9ac99c7332a184__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_29c3cfe7e94e4881__v2.2.json`
- config: `gold_audio_repeat_v2_sol_max` (model=gpt-5.6-sol, effort=max)
- tasks: 3/3 (errors=0)

## Quality
- avg_score_pct: **46.07**
- critical_item_pass_rate: **0.5**
- judge_pass_rate: 0.4074
- judge_error_rate: 0.037
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-09-02T18:56:00+00:00 → 2026-09-02T19:14:27+00:00
- **wall-clock**: 18.4 min
- sum judge latency: 30.1 min (concurrency factor ≈ 1.64x)
- per-task: avg=601.0s, p50=640.0s, p95=702.9s

## Volume
- total API calls: 346 (main=320, perception=26)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=865,814  out=78,940
- main tokens: in=854,572 out=77,028; perception tokens: in=11,242 out=1,912
- render: calls=0, latency=0.0 min; usage_complete=True
- per-task avg (in,out): (288605, 26313)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `38889c3b-e3d4-49c8-816a-3cc8e5313aba` | 707.87 | 105 / 296093,33962,229484 / 687.37s | 0 / 0,0,0 / 0.0s | 7 / 3054,530,0 / 15.48s | 0 / 0,0,0 / 0.0s | none |
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 461.74 | 99 / 252699,18398,216446 / 444.86s | 0 / 0,0,0 / 0.0s | 7 / 2945,498,0 / 15.34s | 0 / 0,0,0 / 0.0s | required_visual_render_target_unavailable:1 |
| `75401f7c-396d-406d-b08e-938874ad1045` | 645.23 | 116 / 305780,24668,264396 / 611.65s | 0 / 0,0,0 / 0.0s | 12 / 5243,884,0 / 28.35s | 0 / 0,0,0 / 0.0s | required_visual_render_target_unavailable:3 |

- judge_error_types: required_visual_render_target_unavailable:4
- projected_220_wall_hours: 36.97 (below_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: unpriced (gpt-5.6-sol,gpt-audio-1.5)
- effective (cached-discounted): unpriced (gpt-5.6-sol,gpt-audio-1.5)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `38889c3b-e3d4-49c8-816a-3cc8e5313aba` | 702.9 | 112 | (299147, 34492) | 70.0 | False |
| `75401f7c-396d-406d-b08e-938874ad1045` | 640.0 | 128 | (311023, 25552) | 48.21 | True |
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 460.2 | 106 | (255644, 18896) | 20.0 | True |
