# Grade Run Analysis — exp003_GPT52Chat_baseline_runner_exec

- file: `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json`
- config: `default_v2_mini` (model=gpt-5.4-mini, effort=medium)
- tasks: 10/10 (errors=0)

## Quality
- avg_score_pct: **59.48**
- critical_item_pass_rate: **0.5**
- judge_pass_rate: 0.4493
- judge_error_rate: 0.0121
- precheck_pass_rate: 1.0

## Wall-clock & latency
- first→last graded_at: 2026-05-30T15:42:53+00:00 → 2026-05-30T16:35:03+00:00
- **wall-clock**: 52.2 min
- sum judge latency: 66.8 min (concurrency factor ≈ 1.28x)
- per-task: avg=400.7s, p50=424.3s, p95=877.6s

## Volume
- judge calls: 414  |  precheck decisions: 25  (judge share 94.3%)
- tokens: in=11,144,398  out=319,157
- per-task avg (in,out): (1114440, 31916)

## Cost estimate
- raw: $3.11  (model=gpt-5.4-mini; in=$2.79, out=$0.32)
- effective (cached-discounted): $2.48  (cache_hit_ratio=45.2%, cached_tokens=5,038,592)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `83d10b06-26d1-4636-a32c-23f92c57f30b` | 877.6 | 36 | (3036127, 34277) | 50.63 | True |
| `43dc9778-450b-4b46-b77e-b6d82b202035` | 658.2 | 67 | (2784812, 60963) | 14.88 | True |
| `c44e9b62-7cd8-4f72-8ad9-f8fbddb94083` | 530.3 | 40 | (2990195, 33210) | 61.85 | True |
| `ee09d943-5a11-430a-b7a2-971b4e9b01b5` | 472.3 | 40 | (547352, 56705) | 58.98 | False |
| `7d7fc9a7-21a7-4b83-906f-416dea5ad04f` | 469.7 | 49 | (621833, 49592) | 41.58 | True |
