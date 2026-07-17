# Grade Run Analysis — exp003_GPT52Chat_baseline_runner_exec

- file: `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__validation_v2_mini_cohort10__cfg_b11acba425087d85__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f__src_011ef05cf7f7a951__v2.2.json`
- config: `validation_v2_mini_cohort10` (model=gpt-5.4-mini, effort=medium)
- tasks: 10/10 (errors=0)

## Quality
- avg_score_pct: **57.74**
- critical_item_pass_rate: **0.4091**
- judge_pass_rate: 0.4391
- judge_error_rate: 0.0
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-07-17T17:52:39+00:00 → 2026-07-17T19:06:02+00:00
- **wall-clock**: 73.4 min
- sum judge latency: 88.8 min (concurrency factor ≈ 1.21x)
- per-task: avg=533.0s, p50=523.1s, p95=1031.2s

## Volume
- total API calls: 1359 (main=1333, perception=26)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=6,863,732  out=375,850
- main tokens: in=6,833,450 out=369,014; perception tokens: in=30,282 out=6,836
- render: calls=26, latency=0.2 min; usage_complete=True
- per-task avg (in,out): (686373, 37585)

## Cost estimate
- raw: $2.15
- effective (cached-discounted): $1.73  (cache_hit_ratio=49.4%, cached_tokens=3,389,440)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `7d7fc9a7-21a7-4b83-906f-416dea5ad04f` | 1031.2 | 208 | (830488, 96095) | 37.47 | True |
| `83d10b06-26d1-4636-a32c-23f92c57f30b` | 954.4 | 138 | (3088707, 46096) | 52.94 | True |
| `ee09d943-5a11-430a-b7a2-971b4e9b01b5` | 711.1 | 149 | (927922, 50955) | 60.88 | True |
| `43dc9778-450b-4b46-b77e-b6d82b202035` | 699.7 | 214 | (575067, 51916) | 14.63 | False |
| `c44e9b62-7cd8-4f72-8ad9-f8fbddb94083` | 550.3 | 136 | (298965, 38311) | 55.0 | True |
