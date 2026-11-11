# Grade Run Analysis — exp036_sol_fixed5

- file: `data/grades/exp036_sol_fixed5__judge_gpt-5_6-sol__exp036_v2_sol_max__cfg_1794403983325602__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_8708d9206ce4c9c9ba96f8bfba0745e12e597777__src_814d56797e9fc3dc__v2.2.json`
- config: `exp036_v2_sol_max` (model=gpt-5.6-sol, effort=max)
- tasks: 2/5 (errors=3)

## Quality
- avg_score_pct: **83.66**
- critical_item_pass_rate: **0.05**
- judge_pass_rate: 0.3109
- judge_error_rate: 0.5056
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-11-05T14:48:15+00:00 → 2026-11-05T15:14:22+00:00
- **wall-clock**: 26.1 min
- sum judge latency: 24.8 min (concurrency factor ≈ 0.95x)
- per-task: avg=298.2s, p50=0.0s, p95=1097.7s

## Volume
- total API calls: 265 (main=245, perception=20)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=909,034  out=79,457
- main tokens: in=850,323 out=73,930; perception tokens: in=58,711 out=5,527
- render: calls=20, latency=1.2 min; usage_complete=True
- per-task avg (in,out): (181807, 15891)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `02aa1805-c658-4069-8a6a-02dec146063a` | 0.01 | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | selection_error:71 |
| `0112fc9b-c3b2-4084-8993-5a4abb1f54f1` | 0.01 | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | selection_error:55 |
| `2ea2e5b5-257f-42e6-a7dc-93763f28b19d` | 1174.0 | 160 / 603372,55766,432840 / 976.87s | 20 / 58711,5527,0 / 120.85s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `3baa0009-5a60-4ae8-ae99-4955cb328ff3` | 393.28 | 85 / 246951,18164,186205 / 393.24s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | required_visual_render_target_unavailable:9 |
| `0818571f-5ff7-4d39-9d2c-ced5ae44299e` | 0.0 | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |

- judge_error_types: required_visual_render_target_unavailable:9, selection_error:126
- projected_220_wall_hours: 19.16 (below_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: unpriced (gpt-5.6-sol)
- effective (cached-discounted): unpriced (gpt-5.6-sol)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `2ea2e5b5-257f-42e6-a7dc-93763f28b19d` | 1097.7 | 180 | (662083, 61293) | 98.0 | False |
| `3baa0009-5a60-4ae8-ae99-4955cb328ff3` | 393.2 | 85 | (246951, 18164) | 69.33 | False |
| `02aa1805-c658-4069-8a6a-02dec146063a` | 0.0 | 0 | (0, 0) | 0.0 | False |
| `0112fc9b-c3b2-4084-8993-5a4abb1f54f1` | 0.0 | 0 | (0, 0) | 0.0 | False |
| `0818571f-5ff7-4d39-9d2c-ced5ae44299e` | 0.0 | 0 | (0, 0) | 0.0 | True |
