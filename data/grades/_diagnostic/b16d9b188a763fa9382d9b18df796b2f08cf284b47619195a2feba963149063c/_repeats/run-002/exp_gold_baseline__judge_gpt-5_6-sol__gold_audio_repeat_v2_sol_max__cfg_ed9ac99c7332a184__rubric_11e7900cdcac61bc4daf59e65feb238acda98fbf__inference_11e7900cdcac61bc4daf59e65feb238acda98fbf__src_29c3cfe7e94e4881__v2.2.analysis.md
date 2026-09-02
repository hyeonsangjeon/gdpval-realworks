# Grade Run Analysis — exp_gold_baseline

- file: `data/grades/_diagnostic/b16d9b188a763fa9382d9b18df796b2f08cf284b47619195a2feba963149063c/_repeats/run-002/exp_gold_baseline__judge_gpt-5_6-sol__gold_audio_repeat_v2_sol_max__cfg_ed9ac99c7332a184__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_29c3cfe7e94e4881__v2.2.json`
- config: `gold_audio_repeat_v2_sol_max` (model=gpt-5.6-sol, effort=max)
- tasks: 3/3 (errors=0)

## Quality
- avg_score_pct: **45.1**
- critical_item_pass_rate: **0.5**
- judge_pass_rate: 0.3981
- judge_error_rate: 0.037
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-09-02T19:36:22+00:00 → 2026-09-02T19:56:45+00:00
- **wall-clock**: 20.4 min
- sum judge latency: 31.3 min (concurrency factor ≈ 1.53x)
- per-task: avg=625.6s, p50=661.8s, p95=695.4s

## Volume
- total API calls: 351 (main=325, perception=26)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=883,525  out=80,705
- main tokens: in=872,283 out=78,808; perception tokens: in=11,242 out=1,897
- render: calls=0, latency=0.0 min; usage_complete=True
- per-task avg (in,out): (294508, 26902)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `38889c3b-e3d4-49c8-816a-3cc8e5313aba` | 669.0 | 106 / 301340,32083,237582 / 648.31s | 0 / 0,0,0 / 0.0s | 7 / 3054,542,0 / 13.52s | 0 / 0,0,0 / 0.0s | none |
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 521.13 | 97 / 247433,18902,180544 / 506.44s | 0 / 0,0,0 / 0.0s | 7 / 2945,493,0 / 13.11s | 0 / 0,0,0 / 0.0s | required_visual_render_target_unavailable:1 |
| `75401f7c-396d-406d-b08e-938874ad1045` | 701.57 | 122 / 323510,27823,246254 / 672.77s | 0 / 0,0,0 / 0.0s | 12 / 5243,862,0 / 22.63s | 0 / 0,0,0 / 0.0s | required_visual_render_target_unavailable:3 |

- judge_error_types: required_visual_render_target_unavailable:4
- projected_220_wall_hours: 38.53 (below_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: unpriced (gpt-5.6-sol,gpt-audio-1.5)
- effective (cached-discounted): unpriced (gpt-5.6-sol,gpt-audio-1.5)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `75401f7c-396d-406d-b08e-938874ad1045` | 695.4 | 134 | (328753, 28685) | 41.96 | True |
| `38889c3b-e3d4-49c8-816a-3cc8e5313aba` | 661.8 | 113 | (304394, 32625) | 70.0 | False |
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 519.5 | 104 | (250378, 19395) | 23.33 | True |
