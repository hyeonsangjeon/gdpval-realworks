# Grade Run Analysis — exp003_GPT52Chat_baseline_runner_exec

- file: `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools.json`
- config: `default_v2` (model=gpt-5.4, effort=medium)
- tasks: 10/10 (errors=0)

## Quality
- avg_score_pct: **56.66**
- critical_item_pass_rate: **0.4091**
- judge_pass_rate: 0.3816
- judge_error_rate: 0.0072
- precheck_pass_rate: 1.0

## Wall-clock & latency
- first→last graded_at: 2026-05-30T08:11:17+00:00 → 2026-05-30T09:15:13+00:00
- **wall-clock**: 63.9 min
- sum judge latency: 75.5 min (concurrency factor ≈ 1.18x)
- per-task: avg=452.8s, p50=490.3s, p95=766.7s

## Volume
- judge calls: 414  |  precheck decisions: 25  (judge share 94.3%)
- tokens: in=4,955,382  out=293,268
- per-task avg (in,out): (495538, 29327)

## Cost estimate
- $7.66  (model=gpt-5.4; in=$6.19, out=$1.47)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `7d7fc9a7-21a7-4b83-906f-416dea5ad04f` | 766.7 | 49 | (529481, 55045) | 44.11 | True |
| `83d10b06-26d1-4636-a32c-23f92c57f30b` | 692.6 | 36 | (2121720, 37297) | 53.33 | True |
| `43dc9778-450b-4b46-b77e-b6d82b202035` | 689.3 | 67 | (549014, 46195) | 10.83 | True |
| `ee09d943-5a11-430a-b7a2-971b4e9b01b5` | 594.5 | 40 | (555844, 41508) | 48.22 | True |
| `7b08cd4d-df60-41ae-9102-8aaa49306ba2` | 561.3 | 59 | (299619, 34643) | 12.98 | True |
