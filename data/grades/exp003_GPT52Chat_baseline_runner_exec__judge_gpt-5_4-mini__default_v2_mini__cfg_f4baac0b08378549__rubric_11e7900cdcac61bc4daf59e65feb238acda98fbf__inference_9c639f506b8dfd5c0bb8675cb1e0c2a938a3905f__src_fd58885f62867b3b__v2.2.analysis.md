# Grade Run Analysis — exp003_GPT52Chat_baseline_runner_exec

- file: `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__default_v2_mini__cfg_f4baac0b08378549__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f__src_fd58885f62867b3b__v2.2.json`
- config: `default_v2_mini` (model=gpt-5.4-mini, effort=medium)
- tasks: 1/1 (errors=0)

## Quality
- avg_score_pct: **50.63**
- critical_item_pass_rate: **0.0**
- judge_pass_rate: 0.4167
- judge_error_rate: 0.0
- precheck_pass_rate: 1.0

## Wall-clock & latency
- first→last graded_at: 2026-07-15T17:25:16+00:00 → 2026-07-15T17:25:16+00:00
- **wall-clock**: None min
- sum judge latency: 13.9 min (concurrency factor ≈ 139.0x)
- per-task: avg=834.1s, p50=834.1s, p95=834.1s

## Volume
- total API calls: 128 (main=127, perception=1)  |  precheck decisions: 5  (judge share 96.2%)
- tokens: in=2,834,829  out=43,822
- main tokens: in=2,833,647 out=43,646; perception tokens: in=1,182 out=176
- render: calls=1, latency=0.0 min; usage_complete=True
- per-task avg (in,out): (2834829, 43822)

## Cost estimate
- raw: $0.75
- effective (cached-discounted): $0.64  (cache_hit_ratio=32.2%, cached_tokens=913,152)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `83d10b06-26d1-4636-a32c-23f92c57f30b` | 834.1 | 128 | (2834829, 43822) | 50.63 | True |
