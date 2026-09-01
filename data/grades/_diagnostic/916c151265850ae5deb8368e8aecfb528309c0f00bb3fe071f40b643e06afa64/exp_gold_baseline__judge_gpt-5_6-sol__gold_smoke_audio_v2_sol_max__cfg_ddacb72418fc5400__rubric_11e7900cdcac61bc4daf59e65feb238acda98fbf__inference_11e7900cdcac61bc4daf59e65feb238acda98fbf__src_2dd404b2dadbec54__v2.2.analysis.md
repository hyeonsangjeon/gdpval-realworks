# Grade Run Analysis — exp_gold_baseline

- file: `data/grades/_diagnostic/916c151265850ae5deb8368e8aecfb528309c0f00bb3fe071f40b643e06afa64/exp_gold_baseline__judge_gpt-5_6-sol__gold_smoke_audio_v2_sol_max__cfg_ddacb72418fc5400__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_2dd404b2dadbec54__v2.2.json`
- config: `gold_smoke_audio_v2_sol_max` (model=gpt-5.6-sol, effort=max)
- tasks: 2/2 (errors=0)

## Quality
- avg_score_pct: **31.87**
- critical_item_pass_rate: **0.5**
- judge_pass_rate: 0.1507
- judge_error_rate: 0.411
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-08-31T09:29:00+00:00 → 2026-08-31T10:01:14+00:00
- **wall-clock**: 32.2 min
- sum judge latency: 74.6 min (concurrency factor ≈ 2.32x)
- per-task: avg=2239.5s, p50=2239.5s, p95=2549.4s

## Volume
- total API calls: 212 (main=210, perception=2)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=508,890  out=42,238
- main tokens: in=508,890 out=42,238; perception tokens: in=0 out=0
- render: calls=0, latency=0.0 min; usage_complete=False
- per-task avg (in,out): (254445, 21119)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 2550.57 | 96 / 224386,19895,185846 / 2548.79s | 0 / 0,0,0 / 0.0s | 1 / 0,0,0 / 0.57s | 0 / 0,0,0 / 0.0s | InternalServerError:7, audio_perception_failed:5, required_visual_render_target_unavailable:1 |
| `75401f7c-396d-406d-b08e-938874ad1045` | 1933.99 | 114 / 284504,22343,244402 / 1929.12s | 0 / 0,0,0 / 0.0s | 1 / 0,0,0 / 0.47s | 0 / 0,0,0 / 0.0s | InternalServerError:4, audio_perception_failed:10, required_visual_render_target_unavailable:3 |

- judge_error_types: InternalServerError:11, audio_perception_failed:15, required_visual_render_target_unavailable:4
- projected_220_wall_hours: 137.03 (at_or_above_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: unpriced (gpt-5.6-sol)
- effective (cached-discounted): unpriced (gpt-5.6-sol)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `e222075d-5d62-4757-ae3c-e34b0846583b` | 2549.4 | 97 | (224386, 19895) | 18.6 | True |
| `75401f7c-396d-406d-b08e-938874ad1045` | 1929.6 | 115 | (284504, 22343) | 45.14 | True |
