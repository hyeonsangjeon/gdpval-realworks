# Grade Run Analysis — exp003_GPT52Chat_baseline_runner_exec

- file: `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__validation_v2_mini_cohort3__cfg_0f76ea22614bdc13__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f__src_86a0061a58077438__v2.2.json`
- config: `validation_v2_mini_cohort3` (model=gpt-5.4-mini, effort=medium)
- tasks: 3/3 (errors=0)

## Quality
- avg_score_pct: **33.3**
- critical_item_pass_rate: **0.0**
- judge_pass_rate: 0.2708
- judge_error_rate: 0.0
- precheck_pass_rate: 0.3333

## Wall-clock & latency
- first→last graded_at: 2026-07-17T06:36:06+00:00 → 2026-07-17T06:57:32+00:00
- **wall-clock**: 21.4 min
- sum judge latency: 37.3 min (concurrency factor ≈ 1.74x)
- per-task: avg=747.0s, p50=792.1s, p95=959.2s

## Volume
- total API calls: 494 (main=490, perception=4)  |  precheck decisions: 12  (judge share 97.6%)
- tokens: in=4,369,788  out=154,166
- main tokens: in=4,365,037 out=153,196; perception tokens: in=4,751 out=970
- render: calls=4, latency=0.1 min; usage_complete=True
- per-task avg (in,out): (1456596, 51389)

## Cost estimate
- raw: $1.26
- effective (cached-discounted): $1.02  (cache_hit_ratio=43.8%, cached_tokens=1,914,368)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `83d10b06-26d1-4636-a32c-23f92c57f30b` | 959.2 | 132 | (3143673, 44287) | 54.76 | True |
| `7d7fc9a7-21a7-4b83-906f-416dea5ad04f` | 792.1 | 181 | (832547, 75986) | 32.11 | True |
| `7b08cd4d-df60-41ae-9102-8aaa49306ba2` | 489.6 | 181 | (393568, 33893) | 13.03 | True |
