# Grade Run Analysis — exp026c_cost_receipt_smoke

- file: `data/grades/_diagnostic/17e2607b1a293be8802a36f1c1ca8e75b96e3437f99d707bfac13d9a9af247b1/exp026c_cost_receipt_smoke__judge_gpt-5_4__cost_smoke_exp026c_v2_gpt54__cfg_c4348e8fa153ce8d__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_0d1d6df224d71aec23a0199ba1e7b272044b500b__src_7ca55f907056df2d__v2.2.json`
- config: `cost_smoke_exp026c_v2_gpt54` (model=gpt-5.4, effort=medium)
- tasks: 1/1 (errors=0)

## Quality
- avg_score_pct: **74.41**
- critical_item_pass_rate: **1.0**
- judge_pass_rate: 0.6316
- judge_error_rate: 0.0
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-09-01T05:25:41+00:00 → 2026-09-01T05:25:41+00:00
- **wall-clock**: None min
- sum judge latency: 7.1 min (concurrency factor ≈ 71.0x)
- per-task: avg=423.2s, p50=423.2s, p95=423.2s

## Volume
- total API calls: 84 (main=83, perception=1)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=302,038  out=24,982
- main tokens: in=300,856 out=24,789; perception tokens: in=1,182 out=193
- render: calls=1, latency=0.0 min; usage_complete=True
- per-task avg (in,out): (302038, 24982)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `83d10b06-26d1-4636-a32c-23f92c57f30b` | 424.77 | 83 / 300856,24789,167424 / 420.02s | 1 / 1182,193,0 / 3.13s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |

- judge_error_types: none
- projected_220_wall_hours: 25.96 (below_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: $0.50
- effective (cached-discounted): $0.40  (cache_hit_ratio=55.4%, cached_tokens=167,424)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `83d10b06-26d1-4636-a32c-23f92c57f30b` | 423.2 | 84 | (302038, 24982) | 74.41 | False |
