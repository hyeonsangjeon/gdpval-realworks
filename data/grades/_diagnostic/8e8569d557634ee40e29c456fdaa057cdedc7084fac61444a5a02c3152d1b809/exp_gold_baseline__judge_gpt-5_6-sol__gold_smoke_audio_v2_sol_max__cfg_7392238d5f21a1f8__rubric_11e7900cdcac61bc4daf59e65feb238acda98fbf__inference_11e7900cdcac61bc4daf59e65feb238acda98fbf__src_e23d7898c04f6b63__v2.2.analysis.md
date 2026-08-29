# Grade Run Analysis — exp_gold_baseline

- file: `data/grades/_diagnostic/8e8569d557634ee40e29c456fdaa057cdedc7084fac61444a5a02c3152d1b809/exp_gold_baseline__judge_gpt-5_6-sol__gold_smoke_audio_v2_sol_max__cfg_7392238d5f21a1f8__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_e23d7898c04f6b63__v2.2.json`
- config: `gold_smoke_audio_v2_sol_max` (model=gpt-5.6-sol, effort=max)
- tasks: 1/1 (errors=0)

## Quality
- avg_score_pct: **26.79**
- critical_item_pass_rate: **0.0**
- judge_pass_rate: 0.15
- judge_error_rate: 0.075
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-08-29T16:32:52+00:00 → 2026-08-29T16:32:52+00:00
- **wall-clock**: None min
- sum judge latency: 9.0 min (concurrency factor ≈ 90.0x)
- per-task: avg=537.9s, p50=537.9s, p95=537.9s

## Volume
- total API calls: 120 (main=120, perception=0)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=302,431  out=23,560
- main tokens: in=302,431 out=23,560; perception tokens: in=0 out=0
- render: calls=0, latency=0.0 min; usage_complete=True
- per-task avg (in,out): (302431, 23560)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `75401f7c-396d-406d-b08e-938874ad1045` | 543.77 | 120 / 302431,23560,263737 / 537.89s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | required_visual_render_target_unavailable:3 |

- judge_error_types: required_visual_render_target_unavailable:3
- projected_220_wall_hours: 33.23 (below_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: unpriced (gpt-5.6-sol)
- effective (cached-discounted): unpriced (gpt-5.6-sol)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `75401f7c-396d-406d-b08e-938874ad1045` | 537.9 | 120 | (302431, 23560) | 26.79 | True |
