# Grade Run Analysis — exp_gold_baseline

- file: `data/grades/_diagnostic/b16d9b188a763fa9382d9b18df796b2f08cf284b47619195a2feba963149063c/_repeats/run-003/exp_gold_baseline__judge_gpt-5_6-sol__gold_audio_repeat_v2_sol_max__cfg_ed9ac99c7332a184__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_29c3cfe7e94e4881__v2.2.json`
- config: `gold_audio_repeat_v2_sol_max` (model=gpt-5.6-sol, effort=max)
- tasks: 3/3 (errors=0)

## Quality
- avg_score_pct: **44.23**
- critical_item_pass_rate: **0.5**
- judge_pass_rate: 0.3796
- judge_error_rate: 0.037
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-09-02T20:21:59+00:00 → 2026-09-02T20:39:34+00:00
- **wall-clock**: 17.6 min
- sum judge latency: 27.1 min (concurrency factor ≈ 1.54x)
- per-task: avg=541.0s, p50=568.1s, p95=577.8s

## Volume
- total API calls: 342 (main=315, perception=27)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=845,605  out=74,565
- main tokens: in=833,912 out=72,576; perception tokens: in=11,693 out=1,989
- render: calls=0, latency=0.0 min; usage_complete=True
- per-task avg (in,out): (281868, 24855)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `38889c3b-e3d4-49c8-816a-3cc8e5313aba` | 585.76 | 102 / 281156,29620,226931 / 561.26s | 0 / 0,0,0 / 0.0s | 8 / 3505,591,0 / 16.54s | 0 / 0,0,0 / 0.0s | none |
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 479.54 | 98 / 249973,18503,215947 / 462.76s | 0 / 0,0,0 / 0.0s | 7 / 2945,493,0 / 14.47s | 0 / 0,0,0 / 0.0s | required_visual_render_target_unavailable:1 |
| `75401f7c-396d-406d-b08e-938874ad1045` | 575.51 | 115 / 302783,24453,261594 / 544.39s | 0 / 0,0,0 / 0.0s | 12 / 5243,905,0 / 23.73s | 0 / 0,0,0 / 0.0s | required_visual_render_target_unavailable:3 |

- judge_error_types: required_visual_render_target_unavailable:4
- projected_220_wall_hours: 33.42 (below_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: unpriced (gpt-5.6-sol,gpt-audio-1.5)
- effective (cached-discounted): unpriced (gpt-5.6-sol,gpt-audio-1.5)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `38889c3b-e3d4-49c8-816a-3cc8e5313aba` | 577.8 | 110 | (284661, 30211) | 70.16 | False |
| `75401f7c-396d-406d-b08e-938874ad1045` | 568.1 | 127 | (308026, 25358) | 44.21 | True |
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 477.2 | 105 | (252918, 18996) | 18.33 | True |
