# Grade Run Analysis — exp003_GPT52Chat_baseline_runner_exec

- file: `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools.json`
- config: `default_v2` (model=gpt-5.4, effort=medium)
- tasks: 10/10 (errors=0)

## Quality
- avg_score_pct: **57.2**
- critical_item_pass_rate: **0.5**
- judge_pass_rate: 0.3913
- judge_error_rate: 0.0024
- precheck_pass_rate: 1.0

## Wall-clock & latency
- first→last graded_at: 2026-05-30T14:25:23+00:00 → 2026-05-30T15:23:27+00:00
- **wall-clock**: 58.1 min
- sum judge latency: 72.7 min (concurrency factor ≈ 1.25x)
- per-task: avg=436.0s, p50=444.2s, p95=875.6s

## Volume
- judge calls: 414  |  precheck decisions: 25  (judge share 94.3%)
- tokens: in=6,207,598  out=265,717
- per-task avg (in,out): (620760, 26572)

## Cost estimate
- raw: $9.09  (model=gpt-5.4; in=$7.76, out=$1.33)
- effective (cached-discounted): $7.86  (cache_hit_ratio=31.6%, cached_tokens=1,963,520)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `83d10b06-26d1-4636-a32c-23f92c57f30b` | 875.6 | 36 | (2945554, 35406) | 50.0 | True |
| `7d7fc9a7-21a7-4b83-906f-416dea5ad04f` | 663.0 | 49 | (560145, 47985) | 42.0 | True |
| `43dc9778-450b-4b46-b77e-b6d82b202035` | 653.8 | 67 | (541422, 43891) | 12.23 | True |
| `ee09d943-5a11-430a-b7a2-971b4e9b01b5` | 544.5 | 40 | (665538, 35135) | 57.97 | False |
| `7b08cd4d-df60-41ae-9102-8aaa49306ba2` | 465.9 | 59 | (321341, 29519) | 15.06 | True |
