# Grade Run Analysis — exp998_smoke_baseline_sample

- file: `data/grades/exp998_smoke_baseline_sample__judge_gpt-5_4__rubric_v2_tools.json`
- config: `default_v2` (model=gpt-5.4, effort=medium)
- tasks: 3/3 (errors=0)

## Quality
- avg_score_pct: **85.5**
- critical_item_pass_rate: **0.0**
- judge_pass_rate: 0.631
- judge_error_rate: 0.0119
- precheck_pass_rate: 0.8

## Wall-clock & latency
- first→last graded_at: 2026-05-30T13:48:48+00:00 → 2026-05-30T13:58:50+00:00
- **wall-clock**: 10.0 min
- sum judge latency: 11.4 min (concurrency factor ≈ 1.14x)
- per-task: avg=227.2s, p50=248.0s, p95=353.9s

## Volume
- judge calls: 84  |  precheck decisions: 18  (judge share 82.4%)
- tokens: in=398,629  out=43,359
- per-task avg (in,out): (132876, 14453)

## Cost estimate
- raw: $0.72  (model=gpt-5.4; in=$0.50, out=$0.22)
- effective (cached-discounted): $0.57  (cache_hit_ratio=59.5%, cached_tokens=237,184)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `0419f1c3-d669-45d0-81cd-f4d5923b06a5` | 353.9 | 49 | (189536, 21997) | 75.06 | True |
| `dfb4e0cd-a0b7-454e-b943-0dd586c2764c` | 248.0 | 20 | (148954, 16928) | 93.95 | False |
| `a328feea-47db-4856-b4be-2bdc63dd88fb` | 79.6 | 15 | (60139, 4434) | 87.5 | False |
