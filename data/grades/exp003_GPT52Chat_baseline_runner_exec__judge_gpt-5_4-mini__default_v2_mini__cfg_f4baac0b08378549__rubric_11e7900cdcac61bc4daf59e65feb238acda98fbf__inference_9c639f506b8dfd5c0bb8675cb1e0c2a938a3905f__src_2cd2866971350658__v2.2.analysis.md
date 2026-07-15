# Grade Run Analysis — exp003_GPT52Chat_baseline_runner_exec

- file: `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__default_v2_mini__cfg_f4baac0b08378549__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f__src_2cd2866971350658__v2.2.json`
- config: `default_v2_mini` (model=gpt-5.4-mini, effort=medium)
- tasks: 1/1 (errors=0)

## Quality
- avg_score_pct: **100.0**
- critical_item_pass_rate: **0.0**
- judge_pass_rate: 0.0
- judge_error_rate: 1.0
- precheck_pass_rate: 1.0

## Wall-clock & latency
- first→last graded_at: 2026-07-15T14:45:48+00:00 → 2026-07-15T14:45:48+00:00
- **wall-clock**: None min
- sum judge latency: 0.2 min (concurrency factor ≈ 2.0x)
- per-task: avg=13.8s, p50=13.8s, p95=13.8s

## Volume
- total API calls: 36 (main=35, perception=1)  |  precheck decisions: 5  (judge share 87.8%)
- tokens: in=1,108  out=248
- main tokens: in=0 out=0; perception tokens: in=1,108 out=248
- render: calls=1, latency=0.0 min; usage_complete=False
- per-task avg (in,out): (1108, 248)

## Cost estimate
- raw: $0.00
- effective (cached-discounted): $0.00  (cache_hit_ratio=0.0%, cached_tokens=0)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `83d10b06-26d1-4636-a32c-23f92c57f30b` | 13.8 | 36 | (1108, 248) | 100.0 | False |
