# Grade Run Analysis — exp003_GPT52Chat_baseline_runner_exec

- file: `data/grades/exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-hybrid__11e7900__v1.json`
- config: `validation_hybrid` (model=gpt-5.4, effort=medium)
- tasks: 219/220 (errors=1)

## Quality
- avg_score_pct: **49.25**
- critical_item_pass_rate: **0.4206**
- judge_pass_rate: 0.3329
- judge_error_rate: 0.006
- precheck_pass_rate: 0.8384

## Wall-clock & latency
- first→last graded_at: 2026-05-27T09:46:48+00:00 → 2026-05-28T21:27:56+00:00
- **wall-clock**: 2141.1 min
- sum judge latency: 2109.0 min (concurrency factor ≈ 0.99x)
- per-task: avg=575.2s, p50=467.3s, p95=1646.5s

## Volume
- judge calls: 9821  |  precheck decisions: 548  (judge share 94.7%)
- tokens: in=18,036,992  out=5,173,299
- per-task avg (in,out): (81986, 23515)

## Cost estimate
- $48.41  (model=gpt-5.4; in=$22.55, out=$25.87)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `8c823e32-537c-42b2-84ba-635d63c2853a` | 3174.0 | 32 | (42156, 29706) | 49.6 | False |
| `0818571f-5ff7-4d39-9d2c-ced5ae44299e` | 3032.6 | 32 | (79621, 58891) | 59.61 | False |
| `11dcc268-cb07-4d3a-a184-c6d7a19349bc` | 3006.5 | 27 | (62980, 30444) | 100.0 | False |
| `e4f664ea-0e5c-4e4e-a0d3-a87a33da947a` | 2656.2 | 48 | (88336, 42935) | 60.36 | False |
| `6241e678-4ba3-4831-b3c7-78412697febc` | 2592.3 | 60 | (81451, 47079) | 38.32 | False |
