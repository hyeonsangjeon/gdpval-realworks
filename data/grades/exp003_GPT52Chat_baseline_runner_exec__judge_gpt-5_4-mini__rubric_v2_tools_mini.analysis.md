# Grade Run Analysis — exp003_GPT52Chat_baseline_runner_exec

- file: `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json`
- config: `default_v2_mini` (model=gpt-5.4-mini, effort=medium)
- tasks: 215/220 (errors=5)

## Quality
- avg_score_pct: **54.1**
- critical_item_pass_rate: **0.528**
- judge_pass_rate: 0.4469
- judge_error_rate: 0.0356
- precheck_pass_rate: 0.5832

## Wall-clock & latency
- first→last graded_at: 2026-06-03T19:01:56+00:00 → 2026-06-04T10:38:41+00:00
- **wall-clock**: 936.8 min
- sum judge latency: 941.2 min (concurrency factor ≈ 1.0x)
- per-task: avg=256.7s, p50=230.9s, p95=651.6s

## Volume
- judge calls: 8904  |  precheck decisions: 539  (judge share 94.3%)
- tokens: in=130,092,056  out=5,523,697
- per-task avg (in,out): (591328, 25108)

## Cost estimate
- raw: $38.05  (model=gpt-5.4-mini; in=$32.52, out=$5.52)
- effective (cached-discounted): $29.24  (cache_hit_ratio=54.2%, cached_tokens=70,480,128)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `6241e678-4ba3-4831-b3c7-78412697febc` | 1916.3 | 60 | (11710955, 108256) | 64.52 | True |
| `b1a79ce1-86b0-41fb-97dc-9206dfd7b044` | 978.4 | 35 | (6305224, 151661) | 39.62 | False |
| `f9a1c16c-53fd-4c8f-88cc-5c325ec2f0bb` | 835.3 | 51 | (5271093, 89418) | 66.84 | True |
| `93b336f3-61f3-4287-86d2-87445e1e0f90` | 798.7 | 52 | (263867, 20394) | 72.89 | False |
| `4520f882-715a-482d-8e87-1cb3cbdfe975` | 779.0 | 87 | (871203, 84002) | 11.09 | True |
