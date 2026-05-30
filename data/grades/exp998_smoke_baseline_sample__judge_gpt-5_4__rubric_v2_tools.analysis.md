# Grade Run Analysis — exp998_smoke_baseline_sample

- file: `data/grades/exp998_smoke_baseline_sample__judge_gpt-5_4__rubric_v2_tools.json`
- config: `default_v2` (model=gpt-5.4, effort=medium)
- tasks: 3/3 (errors=0)

## Quality
- avg_score_pct: **84.16**
- critical_item_pass_rate: **0.0**
- judge_pass_rate: 0.619
- judge_error_rate: 0.0119
- precheck_pass_rate: 0.8

## Wall-clock & latency
- first→last graded_at: 2026-05-30T07:46:00+00:00 → 2026-05-30T07:54:59+00:00
- **wall-clock**: 9.0 min
- sum judge latency: 10.3 min (concurrency factor ≈ 1.14x)
- per-task: avg=206.5s, p50=211.3s, p95=328.0s

## Volume
- judge calls: 84  |  precheck decisions: 18  (judge share 82.4%)
- tokens: in=395,836  out=42,525
- per-task avg (in,out): (131945, 14175)

## Cost estimate
- $0.71  (model=gpt-5.4; in=$0.49, out=$0.21)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `0419f1c3-d669-45d0-81cd-f4d5923b06a5` | 328.0 | 49 | (189228, 22139) | 73.12 | True |
| `dfb4e0cd-a0b7-454e-b943-0dd586c2764c` | 211.3 | 20 | (148324, 15528) | 93.95 | False |
| `a328feea-47db-4856-b4be-2bdc63dd88fb` | 80.1 | 15 | (58284, 4858) | 85.42 | False |
