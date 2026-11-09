# Grade Run Analysis — exp035_codex_foundry_full220

- file: `data/grades/_diagnostic/b2ed72124660d52d20ffb3af870fa308a3ebdf3b2bbe4aed9dc495f240ac4851/exp035_codex_foundry_full220__judge_gpt-5_6-sol__e35par__cfg_947381242d273196__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_dc36d6837a8f0899f8bfa4d32aae9a9f6805f3b0__src_02cbcf3824bd89a2__v2.2.json`
- config: `e35par` (model=gpt-5.6-sol, effort=max)
- tasks: 8/8 (errors=0)

## Quality
- avg_score_pct: **77.58**
- critical_item_pass_rate: **0.4444**
- judge_pass_rate: 0.684
- judge_error_rate: 0.0
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-11-09T08:32:20+00:00 → 2026-11-09T09:54:39+00:00
- **wall-clock**: 82.3 min
- sum judge latency: 93.5 min (concurrency factor ≈ 1.14x)
- per-task: avg=701.4s, p50=625.6s, p95=1214.2s

## Volume
- total API calls: 1017 (main=935, perception=82)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=3,996,397  out=296,012
- main tokens: in=3,723,889 out=271,665; perception tokens: in=272,508 out=24,347
- render: calls=82, latency=3.3 min; usage_complete=True
- per-task avg (in,out): (499550, 37002)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `15d37511-75c5-4c7f-81f1-16e00c0d95f3` | 915.54 | 176 / 529957,46000,414086 / 897.36s | 1 / 2777,1058,0 / 16.27s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `15ddd28d-8445-4baa-ac7f-f41372e1344e` | 519.17 | 93 / 327604,29577,199579 / 516.84s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `1aecc095-4d76-4b89-b752-1a0f870502cd` | 740.46 | 134 / 425925,36822,328211 / 696.12s | 4 / 10874,2106,0 / 33.66s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `3baa0009-5a60-4ae8-ae99-4955cb328ff3` | 522.73 | 99 / 279576,23832,217014 / 477.62s | 9 / 15546,1594,0 / 43.76s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `9a8c8e28-ce76-408b-83c3-488422892e58` | 1030.98 | 139 / 528045,37952,314109 / 746.05s | 39 / 108759,11509,0 / 252.99s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `aad21e4c-1d43-45fc-899a-97754a1b1b63` | 1218.42 | 181 / 1225907,74746,423994 / 1214.17s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `b1a79ce1-86b0-41fb-97dc-9206dfd7b044` | 611.96 | 43 / 156233,10540,81773 / 213.16s | 28 / 131839,7897,0 / 210.57s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `cebf301e-5ea7-41ae-b117-ad8f43e7ac22` | 294.57 | 70 / 250642,12196,148419 / 287.75s | 1 / 2713,183,0 / 4.78s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |

- judge_error_types: none
- projected_220_wall_hours: 44.72 (at_or_above_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: unpriced (gpt-5.6-sol)
- effective (cached-discounted): unpriced (gpt-5.6-sol)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `aad21e4c-1d43-45fc-899a-97754a1b1b63` | 1214.2 | 181 | (1225907, 74746) | 89.49 | True |
| `9a8c8e28-ce76-408b-83c3-488422892e58` | 999.0 | 178 | (636804, 49461) | 58.7 | True |
| `15d37511-75c5-4c7f-81f1-16e00c0d95f3` | 913.6 | 177 | (532734, 47058) | 65.76 | True |
| `1aecc095-4d76-4b89-b752-1a0f870502cd` | 729.8 | 138 | (436799, 38928) | 77.64 | True |
| `3baa0009-5a60-4ae8-ae99-4955cb328ff3` | 521.4 | 108 | (295122, 25426) | 70.09 | False |
