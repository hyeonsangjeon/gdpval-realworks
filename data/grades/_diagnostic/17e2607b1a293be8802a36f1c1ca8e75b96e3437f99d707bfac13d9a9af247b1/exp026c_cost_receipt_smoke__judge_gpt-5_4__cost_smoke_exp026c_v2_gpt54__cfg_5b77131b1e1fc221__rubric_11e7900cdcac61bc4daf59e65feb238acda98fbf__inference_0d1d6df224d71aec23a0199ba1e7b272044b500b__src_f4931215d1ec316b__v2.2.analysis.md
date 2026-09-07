# Grade Run Analysis — exp026c_cost_receipt_smoke

- file: `data/grades/_diagnostic/17e2607b1a293be8802a36f1c1ca8e75b96e3437f99d707bfac13d9a9af247b1/exp026c_cost_receipt_smoke__judge_gpt-5_4__cost_smoke_exp026c_v2_gpt54__cfg_5b77131b1e1fc221__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_0d1d6df224d71aec23a0199ba1e7b272044b500b__src_f4931215d1ec316b__v2.2.json`
- config: `cost_smoke_exp026c_v2_gpt54` (model=gpt-5.4, effort=medium)
- tasks: 1/1 (errors=0)

## Quality
- avg_score_pct: **66.41**
- critical_item_pass_rate: **1.0**
- judge_pass_rate: 0.5789
- judge_error_rate: 0.0
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-09-07T13:59:33+00:00 → 2026-09-07T13:59:33+00:00
- **wall-clock**: None min
- sum judge latency: 8.3 min (concurrency factor ≈ 83.0x)
- per-task: avg=498.5s, p50=498.5s, p95=498.5s

## Volume
- total API calls: 112 (main=111, perception=1)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=377,142  out=27,211
- main tokens: in=375,960 out=27,051; perception tokens: in=1,182 out=160
- render: calls=1, latency=0.0 min; usage_complete=True
- per-task avg (in,out): (377142, 27211)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `83d10b06-26d1-4636-a32c-23f92c57f30b` | 500.17 | 111 / 375960,27051,248576 / 492.57s | 1 / 1182,160,0 / 5.95s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |

- judge_error_types: none
- projected_220_wall_hours: 30.57 (below_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: $0.61
- effective (cached-discounted): $0.45  (cache_hit_ratio=65.9%, cached_tokens=248,576)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `83d10b06-26d1-4636-a32c-23f92c57f30b` | 498.5 | 112 | (377142, 27211) | 66.41 | False |
