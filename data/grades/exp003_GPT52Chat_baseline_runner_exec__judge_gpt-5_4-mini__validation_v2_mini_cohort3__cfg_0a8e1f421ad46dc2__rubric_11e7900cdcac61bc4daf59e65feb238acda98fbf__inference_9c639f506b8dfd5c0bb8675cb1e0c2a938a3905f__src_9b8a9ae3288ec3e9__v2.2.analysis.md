# Grade Run Analysis — exp003_GPT52Chat_baseline_runner_exec

- file: `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__validation_v2_mini_cohort3__cfg_0a8e1f421ad46dc2__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f__src_9b8a9ae3288ec3e9__v2.2.json`
- config: `validation_v2_mini_cohort3` (model=gpt-5.4-mini, effort=medium)
- tasks: 3/3 (errors=0)

## Quality
- avg_score_pct: **36.14**
- critical_item_pass_rate: **0.0**
- judge_pass_rate: 0.281
- judge_error_rate: 0.0
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-07-17T10:21:11+00:00 → 2026-07-17T10:46:07+00:00
- **wall-clock**: 24.9 min
- sum judge latency: 41.2 min (concurrency factor ≈ 1.65x)
- per-task: avg=823.4s, p50=942.7s, p95=979.8s

## Volume
- total API calls: 536 (main=532, perception=4)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=4,545,150  out=177,563
- main tokens: in=4,540,399 out=176,531; perception tokens: in=4,751 out=1,032
- render: calls=4, latency=0.0 min; usage_complete=True
- per-task avg (in,out): (1515050, 59188)

## Cost estimate
- raw: $1.32
- effective (cached-discounted): $1.08  (cache_hit_ratio=43.0%, cached_tokens=1,955,328)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `83d10b06-26d1-4636-a32c-23f92c57f30b` | 979.8 | 137 | (3193116, 47667) | 60.32 | True |
| `7d7fc9a7-21a7-4b83-906f-416dea5ad04f` | 942.7 | 221 | (970471, 96677) | 34.05 | True |
| `7b08cd4d-df60-41ae-9102-8aaa49306ba2` | 547.8 | 178 | (381563, 33219) | 14.04 | True |
