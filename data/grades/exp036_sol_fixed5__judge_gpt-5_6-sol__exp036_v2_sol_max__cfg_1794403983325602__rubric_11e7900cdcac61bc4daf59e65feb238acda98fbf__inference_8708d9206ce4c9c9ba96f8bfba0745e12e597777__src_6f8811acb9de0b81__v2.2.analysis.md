# Grade Run Analysis — exp036_sol_fixed5

- file: `data/grades/exp036_sol_fixed5__judge_gpt-5_6-sol__exp036_v2_sol_max__cfg_1794403983325602__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_8708d9206ce4c9c9ba96f8bfba0745e12e597777__src_6f8811acb9de0b81__v2.2.json`
- config: `exp036_v2_sol_max` (model=gpt-5.6-sol, effort=max)
- tasks: 4/5 (errors=1)

## Quality
- avg_score_pct: **90.83**
- critical_item_pass_rate: **0.1364**
- judge_pass_rate: 0.7828
- judge_error_rate: 0.0
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-11-09T08:34:09+00:00 → 2026-11-09T09:08:21+00:00
- **wall-clock**: 34.2 min
- sum judge latency: 51.3 min (concurrency factor ≈ 1.5x)
- per-task: avg=615.6s, p50=496.8s, p95=1082.1s

## Volume
- total API calls: 629 (main=598, perception=31)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=2,018,575  out=151,811
- main tokens: in=1,932,834 out=144,487; perception tokens: in=85,741 out=7,324
- render: calls=31, latency=0.9 min; usage_complete=True
- per-task avg (in,out): (403715, 30362)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `02aa1805-c658-4069-8a6a-02dec146063a` | 1084.07 | 227 / 670328,49248,535222 / 1071.75s | 1 / 2699,615,0 / 10.31s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `0112fc9b-c3b2-4084-8993-5a4abb1f54f1` | 456.36 | 112 / 373519,20239,239194 / 448.03s | 1 / 2701,253,0 / 5.73s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `2ea2e5b5-257f-42e6-a7dc-93763f28b19d` | 1097.23 | 161 / 601810,53981,422943 / 926.71s | 20 / 58711,4853,0 / 118.65s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `3baa0009-5a60-4ae8-ae99-4955cb328ff3` | 498.13 | 98 / 287177,21019,214761 / 430.81s | 9 / 21630,1603,0 / 66.03s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `0818571f-5ff7-4d39-9d2c-ced5ae44299e` | 0.0 | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |

- judge_error_types: none
- projected_220_wall_hours: 38.33 (below_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: unpriced (gpt-5.6-sol)
- effective (cached-discounted): unpriced (gpt-5.6-sol)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `02aa1805-c658-4069-8a6a-02dec146063a` | 1082.1 | 228 | (673027, 49863) | 94.13 | False |
| `2ea2e5b5-257f-42e6-a7dc-93763f28b19d` | 1045.4 | 181 | (660521, 58834) | 98.24 | False |
| `3baa0009-5a60-4ae8-ae99-4955cb328ff3` | 496.8 | 107 | (308807, 22622) | 72.77 | False |
| `0112fc9b-c3b2-4084-8993-5a4abb1f54f1` | 453.8 | 113 | (376220, 20492) | 98.18 | False |
| `0818571f-5ff7-4d39-9d2c-ced5ae44299e` | 0.0 | 0 | (0, 0) | 0.0 | True |
