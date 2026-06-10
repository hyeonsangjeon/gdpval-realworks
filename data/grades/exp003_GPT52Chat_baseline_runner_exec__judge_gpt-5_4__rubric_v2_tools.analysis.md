# Grade Run Analysis — exp003_GPT52Chat_baseline_runner_exec

- file: `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools.json`
- config: `default_v2` (model=gpt-5.4, effort=medium)
- tasks: 215/220 (errors=5)

## Quality
- avg_score_pct: **53.3**
- critical_item_pass_rate: **0.501**
- judge_pass_rate: 0.4154
- judge_error_rate: 0.0276
- precheck_pass_rate: 0.5832

## Wall-clock & latency
- first→last graded_at: 2026-06-09T05:13:16+00:00 → 2026-06-10T18:17:55+00:00
- **wall-clock**: 2224.7 min
- sum judge latency: 1472.3 min (concurrency factor ≈ 0.66x)
- per-task: avg=401.5s, p50=393.6s, p95=891.7s

## Volume
- judge calls: 8904  |  precheck decisions: 539  (judge share 94.3%)
- tokens: in=107,844,571  out=4,652,556
- per-task avg (in,out): (490203, 21148)

## Cost estimate
- raw: $158.07  (model=gpt-5.4; in=$134.81, out=$23.26)
- effective (cached-discounted): $123.37  (cache_hit_ratio=51.5%, cached_tokens=55,525,248)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `6241e678-4ba3-4831-b3c7-78412697febc` | 1676.7 | 60 | (10396202, 72355) | 39.68 | True |
| `b1a79ce1-86b0-41fb-97dc-9206dfd7b044` | 1622.1 | 35 | (6519732, 121294) | 9.43 | False |
| `40a8c4b1-b169-4f92-a38b-7f79685037ec` | 1321.9 | 72 | (782411, 64590) | 36.0 | True |
| `a73fbc98-90d4-4134-a54f-2b1d0c838791` | 1267.3 | 60 | (819631, 72194) | 46.44 | True |
| `47ef842d-8eac-4b90-bda8-dd934c228c96` | 1133.4 | 57 | (4411174, 44065) | 72.48 | True |
