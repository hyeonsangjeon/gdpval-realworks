# Grade Run Analysis — exp999_smoke_baseline_sample

- file: `data/grades/exp999_smoke_baseline_sample__gpt-5_4-mini__11e7900__v1.json`
- config: `default_gpt5pro` (model=gpt-5.4-mini, effort=medium)
- tasks: 1/1 (errors=0)

## Quality
- avg_score_pct: **89.17**
- critical_item_pass_rate: **0.0**
- judge_pass_rate: 0.8125
- judge_error_rate: 0.0
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-07-21T13:53:42+00:00 → 2026-07-21T13:53:42+00:00
- **wall-clock**: None min
- sum judge latency: 1.0 min (concurrency factor ≈ 10.0x)
- per-task: avg=59.5s, p50=59.5s, p95=59.5s

## Volume
- total API calls: 16 (main=16, perception=0)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=17,990  out=4,366
- main tokens: in=17,990 out=4,366; perception tokens: in=0 out=0
- render: calls=0, latency=0.0 min; usage_complete=True
- per-task avg (in,out): (17990, 4366)

## Cost estimate
- raw: $0.01  (model=gpt-5.4-mini; in=$0.00, out=$0.00)
- effective (cached-discounted): $0.01  (cache_hit_ratio=0.0%, cached_tokens=0)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `a328feea-47db-4856-b4be-2bdc63dd88fb` | 59.5 | 16 | (17990, 4366) | 89.17 | False |
