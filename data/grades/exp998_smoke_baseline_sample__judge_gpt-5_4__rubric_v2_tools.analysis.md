# Grade Run Analysis — exp998_smoke_baseline_sample

- file: `data/grades/exp998_smoke_baseline_sample__judge_gpt-5_4__rubric_v2_tools.json`
- config: `default_v2` (model=gpt-5.4, effort=medium)
- tasks: 3/3 (errors=0)

## Quality
- avg_score_pct: **84.62**
- critical_item_pass_rate: **0.0**
- judge_pass_rate: 0.619
- judge_error_rate: 0.0119
- precheck_pass_rate: 0.8

## Wall-clock & latency
- first→last graded_at: 2026-05-30T07:21:14+00:00 → 2026-05-30T07:30:22+00:00
- **wall-clock**: 9.1 min
- sum judge latency: 10.8 min (concurrency factor ≈ 1.19x)
- per-task: avg=215.3s, p50=226.8s, p95=321.0s

## Volume
- judge calls: 84  |  precheck decisions: 18  (judge share 82.4%)
- tokens: in=398,619  out=42,688
- per-task avg (in,out): (132873, 14229)

## Cost estimate
- $0.71  (model=gpt-5.4; in=$0.50, out=$0.21)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `0419f1c3-d669-45d0-81cd-f4d5923b06a5` | 321.0 | 49 | (189192, 21808) | 73.18 | True |
| `dfb4e0cd-a0b7-454e-b943-0dd586c2764c` | 226.8 | 20 | (148900, 15756) | 93.81 | False |
| `a328feea-47db-4856-b4be-2bdc63dd88fb` | 98.1 | 15 | (60527, 5124) | 86.88 | False |
