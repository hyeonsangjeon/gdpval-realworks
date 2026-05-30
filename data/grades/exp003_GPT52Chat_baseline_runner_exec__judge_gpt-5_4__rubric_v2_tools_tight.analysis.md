# Grade Run Analysis — exp003_GPT52Chat_baseline_runner_exec

- file: `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools_tight.json`
- config: `default_v2_tight` (model=gpt-5.4, effort=medium)
- tasks: 10/10 (errors=0)

## Quality
- avg_score_pct: **54.77**
- critical_item_pass_rate: **0.4091**
- judge_pass_rate: 0.3744
- judge_error_rate: 0.0338
- precheck_pass_rate: 1.0

## Wall-clock & latency
- first→last graded_at: 2026-05-30T09:33:08+00:00 → 2026-05-30T10:37:02+00:00
- **wall-clock**: 63.9 min
- sum judge latency: 77.1 min (concurrency factor ≈ 1.21x)
- per-task: avg=462.6s, p50=501.2s, p95=792.5s

## Volume
- judge calls: 414  |  precheck decisions: 25  (judge share 94.3%)
- tokens: in=5,867,216  out=291,827
- per-task avg (in,out): (586722, 29183)

## Cost estimate
- $8.79  (model=gpt-5.4; in=$7.33, out=$1.46)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `83d10b06-26d1-4636-a32c-23f92c57f30b` | 792.5 | 36 | (2490022, 37434) | 41.19 | True |
| `43dc9778-450b-4b46-b77e-b6d82b202035` | 767.8 | 67 | (713999, 50112) | 12.19 | True |
| `7d7fc9a7-21a7-4b83-906f-416dea5ad04f` | 739.8 | 49 | (517799, 50153) | 36.63 | True |
| `ee09d943-5a11-430a-b7a2-971b4e9b01b5` | 591.6 | 40 | (612606, 42879) | 43.56 | True |
| `7b08cd4d-df60-41ae-9102-8aaa49306ba2` | 561.1 | 59 | (311322, 32576) | 12.36 | True |
